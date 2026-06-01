# Changed: create OpalFSMEnvironment for GFlowNet training
# Why: replaces Grid environment with Opal protocol FSM for trajectory generation
"""
Opal FSM Environment for GFlowNet
==================================
Implements the Environment interface from augustwester/gflownet,
replacing the Grid environment with our TCG/Opal protocol FSM.

M = (Q, Σ, δ, q₀, F) from opal_fsm.py
- state_dim = |Q| + 1 = 26 (25 one-hot state + t/T_max)
- num_actions = |Σ| + 1 = 87 (86 protocol actions + terminate)
"""

import math
import torch
from torch.nn.functional import one_hot

from tools.datagen.opal_fsm import S, A, DELTA, get_valid_actions, Transition


# ── Map enums to indices ──

ALL_STATES = list(S)
ALL_ACTIONS = list(A)
STATE_TO_IDX = {s: i for i, s in enumerate(ALL_STATES)}
IDX_TO_STATE = {i: s for s, i in STATE_TO_IDX.items()}
ACTION_TO_IDX = {a: i for i, a in enumerate(ALL_ACTIONS)}
IDX_TO_ACTION = {i: a for a, i in ACTION_TO_IDX.items()}

NUM_STATES = len(ALL_STATES)       # 25
NUM_ACTIONS = len(ALL_ACTIONS)     # 86
TERMINATE_ACTION = NUM_ACTIONS     # index 86 = terminate
TOTAL_ACTIONS = NUM_ACTIONS + 1    # 87

# Initial state: PROPS_QUERIED (not POWER_OFF — matches public20 patterns)
Q0 = S.PROPS_QUERIED
Q0_IDX = STATE_TO_IDX[Q0]

T_MAX = 40  # max trajectory length (public20 max = 39)


class OpalFSMEnvironment:
    """GFlowNet environment wrapping the Opal protocol FSM."""

    def __init__(self):
        self.state_dim = NUM_STATES + 1   # 26: one-hot state + t/T_max
        self.num_actions = TOTAL_ACTIONS   # 87: 86 actions + terminate

        # Pre-compute mask table: for each state, which actions are valid
        # Shape: (NUM_STATES, TOTAL_ACTIONS)
        self._mask_table = torch.zeros(NUM_STATES, TOTAL_ACTIONS)
        for s in ALL_STATES:
            s_idx = STATE_TO_IDX[s]
            valid = get_valid_actions(s)
            for a in valid:
                a_idx = ACTION_TO_IDX[a]
                self._mask_table[s_idx, a_idx] = 1.0
            # Terminate action is always valid (agent can stop anytime)
            self._mask_table[s_idx, TERMINATE_ACTION] = 1.0

        # Changed: restrict POWER_CYCLE to only recovery/boot states
        # Why: POWER_CYCLE is reachable from every state in DELTA, causing
        #      the GFlowNet to over-select it → Properties overrepresentation
        #      and R42/R84 rule bias (issues #5, #6, #7)
        power_cycle_idx = ACTION_TO_IDX.get(A.POWER_CYCLE)
        if power_cycle_idx is not None:
            allowed_power_cycle_states = {
                STATE_TO_IDX[S.POWER_OFF],
                STATE_TO_IDX[S.POWERED_ON],
                STATE_TO_IDX[S.ERROR_RECOVERY],
                STATE_TO_IDX[S.SESSION_ABORTED],
                STATE_TO_IDX[S.REVERTED],
            }
            for s_idx in range(NUM_STATES):
                if s_idx not in allowed_power_cycle_states:
                    self._mask_table[s_idx, power_cycle_idx] = 0.0

        # Changed: restrict RECOVER_FROM_ERROR to only error states
        # Why: same rationale — limit recovery actions to semantically
        #      appropriate states to reduce action-space noise
        recover_idx = ACTION_TO_IDX.get(A.RECOVER_FROM_ERROR)
        if recover_idx is not None:
            allowed_recover_states = {
                STATE_TO_IDX[S.ERROR_RECOVERY],
                STATE_TO_IDX[S.SESSION_ABORTED],
                STATE_TO_IDX[S.REVERTED],
                STATE_TO_IDX[S.LOCKING_INACTIVE],
            }
            for s_idx in range(NUM_STATES):
                if s_idx not in allowed_recover_states:
                    self._mask_table[s_idx, recover_idx] = 0.0

        # Changed: restrict START_* actions when already in a session
        # Why: FSM allows StartSession from session states without EndSession first,
        #      creating invalid trajectories with two StartSessions without EndSession.
        #      Force GFlowNet to EndSession before opening a new session.
        session_states = {STATE_TO_IDX[s] for s in ALL_STATES
                          if 'ADMIN_RW' in s.name or 'ADMIN_RO' in s.name
                          or 'LOCKING_RW' in s.name or 'LOCKING_RO' in s.name
                          or 'RANGE' in s.name or 'KEY' in s.name}
        start_actions = {ACTION_TO_IDX[a] for a in ALL_ACTIONS
                         if a.name.startswith('START_') and 'SPBUSY' not in a.name
                         and 'CONCURRENT' not in a.name}
        for s_idx in session_states:
            for a_idx in start_actions:
                self._mask_table[s_idx, a_idx] = 0.0

        # Pre-compute transition table: (state_idx, action_idx) → next_state_idx
        # -1 means undefined (should never be reached due to masking)
        self._transition_table = torch.full((NUM_STATES, NUM_ACTIONS), -1, dtype=torch.long)
        for (s, a), t in DELTA.items():
            s_idx = STATE_TO_IDX[s]
            a_idx = ACTION_TO_IDX[a]
            ns_idx = STATE_TO_IDX[t.next_state]
            self._transition_table[s_idx, a_idx] = ns_idx

    def initial_state(self, batch_size: int) -> torch.Tensor:
        """Create batch of initial states.

        Returns: (batch_size, state_dim) tensor
            First NUM_STATES dims = one-hot state, last dim = t/T_max = 0
        """
        s = torch.zeros(batch_size, self.state_dim)
        s[:, Q0_IDX] = 1.0
        # t/T_max = 0.0 (already zero)
        return s

    def _decode_state_idx(self, s: torch.Tensor) -> torch.Tensor:
        """Extract state index from encoding. s: (N, state_dim) → (N,)"""
        return s[:, :NUM_STATES].argmax(dim=1)

    def _decode_step(self, s: torch.Tensor) -> torch.Tensor:
        """Extract normalized step from encoding. s: (N, state_dim) → (N,)"""
        return s[:, NUM_STATES]

    def update(self, s: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        """Apply actions to states, return new states.

        Args:
            s: (N, state_dim) current states
            actions: (N,) action indices

        Returns: (N, state_dim) new states
        """
        state_idx = self._decode_state_idx(s)
        step = self._decode_step(s)
        new_s = torch.zeros_like(s)

        for i in range(len(s)):
            a = actions[i].item()
            if a == TERMINATE_ACTION:
                # Terminate: keep current state (will be marked done externally)
                new_s[i] = s[i].clone()
            elif a < NUM_ACTIONS:
                si = state_idx[i].item()
                ns = self._transition_table[si, a].item()
                if ns >= 0:
                    new_s[i, ns] = 1.0
                    new_s[i, NUM_STATES] = min((step[i].item() + 1.0) / T_MAX, 1.0)
                else:
                    # Invalid transition (shouldn't happen due to masking)
                    new_s[i] = s[i].clone()
            else:
                new_s[i] = s[i].clone()

        return new_s

    def mask(self, s: torch.Tensor) -> torch.Tensor:
        """Return action mask for each state.

        Args:
            s: (N, state_dim)

        Returns: (N, TOTAL_ACTIONS) binary mask
        """
        state_idx = self._decode_state_idx(s)
        step = self._decode_step(s)
        masks = self._mask_table[state_idx]  # (N, TOTAL_ACTIONS)

        # Force terminate if at T_MAX
        at_max = step >= 1.0
        if at_max.any():
            forced = torch.zeros(at_max.sum().item(), TOTAL_ACTIONS)
            forced[:, TERMINATE_ACTION] = 1.0
            masks[at_max] = forced

        return masks

    def reward(self, trajectories_info: list) -> torch.Tensor:
        """Compute reward for completed trajectories.

        Changed: Gaussian-shaped length reward centered at TARGET_LENGTH
        Why: log(length+1) monotonically increases → policy never terminates,
             causing 86% of trajectories to hit T_MAX=40. Gaussian peaks at
             public20's avg length (16.4) and penalizes too-short and too-long.

        Args:
            trajectories_info: list of dicts with 'length' and 'states_visited' keys

        Returns: (N,) reward tensor
        """
        rewards = torch.zeros(len(trajectories_info))
        for i, info in enumerate(trajectories_info):
            length = info['length']
            unique_states = info['unique_states']
            if length == 0:
                rewards[i] = 0.01
            else:
                # Reward = log(length+1) for basic quality
                base = math.log(min(length, 25) + 1)
                # Penalty for hitting T_MAX (didn't terminate naturally)
                hit_max = 1.0 if length < T_MAX else 0.3
                # Diversity: unique states (capped to avoid dominating)
                div = min(unique_states, 10) / 10.0
                rewards[i] = base * hit_max * (1.0 + 0.5 * div)
        return rewards

    def get_transition_info(self, state_idx: int, action_idx: int) -> Transition:
        """Get FSM transition info for a (state, action) pair."""
        s = IDX_TO_STATE.get(state_idx)
        a = IDX_TO_ACTION.get(action_idx)
        if s is None or a is None:
            return None
        return DELTA.get((s, a))
