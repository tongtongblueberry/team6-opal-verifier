# Changed: create GFlowNet trainer for Opal FSM trajectory generation
# Why: implements the FSM-GFlowNet paper's training pipeline adapted for Opal protocol
"""
GFlowNet Training for Opal FSM
================================
Trains a forward policy π_θ to sample diverse, FSM-valid trajectories.

Loss (from paper, p.5 — REINFORCE-style, NOT TB loss):
    L(θ) = -R(τ) · Σ_{t=0}^{|τ|} log π_θ(a_t | s_t)

Key differences from augustwester/gflownet:
    - No backward policy (paper uses REINFORCE loss, not TB loss)
    - ε-greedy exploration (paper p.6)
    - State encoding includes t/T_max (paper p.5)
    - Starting state = PROPS_QUERIED (matches public20)
    - No mouse hover injection (not applicable to Opal protocol)
"""

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical
from torch.optim import Adam

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.datagen.opal_gflownet_env import (
    OpalFSMEnvironment, NUM_STATES, TOTAL_ACTIONS, TERMINATE_ACTION,
    T_MAX, STATE_TO_IDX, IDX_TO_STATE, IDX_TO_ACTION, ACTION_TO_IDX,
)
from tools.datagen.opal_fsm import S, A, DELTA


# ── Forward Policy ──

class ForwardPolicy(nn.Module):
    """2-layer feedforward policy network (same architecture as paper and augustwester)."""

    def __init__(self, state_dim: int, hidden_dim: int, num_actions: int):
        super().__init__()
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, num_actions)

    def forward(self, s: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.fc1(s))
        return F.softmax(self.fc2(x), dim=-1)


# ── GFlowNet (simplified — no backward policy) ──

class OpalGFlowNet(nn.Module):
    """FSM-constrained GFlowNet for Opal trajectory generation.

    Following the paper's formulation (Section IV-C):
    - FSM action masking at every step
    - ε-greedy exploration
    - REINFORCE-style loss (no backward policy)
    """

    def __init__(self, forward_policy: ForwardPolicy, env: OpalFSMEnvironment,
                 epsilon: float = 0.1):
        super().__init__()
        self.forward_policy = forward_policy
        self.env = env
        self.epsilon = epsilon

    def masked_forward_probs(self, s: torch.Tensor) -> torch.Tensor:
        """Compute forward probabilities with FSM action masking.

        π_θ(a_t | s_t) = softmax(f_θ(φ(s_t, t)) + log m_{s_t})
        Implemented as: mask * softmax → renormalize (equivalent, numerically stabler)
        """
        probs = self.forward_policy(s)
        mask = self.env.mask(s)
        probs = probs * mask
        # Re-normalize (avoid division by zero)
        total = probs.sum(dim=-1, keepdim=True).clamp(min=1e-8)
        return probs / total

    def sample_action(self, s: torch.Tensor) -> torch.Tensor:
        """Sample action with ε-greedy exploration (paper p.6).

        With probability ε: uniform random from valid actions
        Otherwise: sample from π_θ
        """
        batch_size = s.shape[0]
        probs = self.masked_forward_probs(s)
        mask = self.env.mask(s)

        actions = torch.zeros(batch_size, dtype=torch.long)
        for i in range(batch_size):
            if random.random() < self.epsilon:
                # ε-greedy: uniform over valid actions
                valid_idx = mask[i].nonzero(as_tuple=True)[0]
                actions[i] = valid_idx[random.randint(0, len(valid_idx) - 1)]
            else:
                # Policy sampling
                actions[i] = Categorical(probs[i]).sample()

        return actions

    def sample_trajectories(self, batch_size: int) -> list:
        """Sample batch of trajectories using current policy with ε-greedy.

        Returns list of dicts, each containing:
            - 'states': list of state tensors
            - 'actions': list of action indices
            - 'log_probs': list of log π_θ(a_t|s_t)
            - 'length': trajectory length
            - 'unique_states': number of unique FSM states visited
        """
        s = self.env.initial_state(batch_size)
        done = torch.zeros(batch_size, dtype=torch.bool)

        # Per-trajectory storage
        trajectories = [{'states': [], 'actions': [], 'log_probs': [],
                         'state_set': set()} for _ in range(batch_size)]

        step = 0
        while not done.all() and step < T_MAX:
            active = ~done
            active_idx = active.nonzero(as_tuple=True)[0]
            active_s = s[active]

            # Compute probabilities for log_prob computation
            probs = self.masked_forward_probs(active_s)

            # Sample with ε-greedy
            actions = self.sample_action(active_s)

            # Record trajectory info
            for j, idx in enumerate(active_idx):
                i = idx.item()
                a = actions[j].item()
                state_idx = active_s[j, :NUM_STATES].argmax().item()

                trajectories[i]['states'].append(active_s[j].detach().clone())
                trajectories[i]['actions'].append(a)
                trajectories[i]['state_set'].add(state_idx)

                # Log probability from policy (not ε-greedy — policy prob only)
                log_p = torch.log(probs[j, a].clamp(min=1e-8))
                trajectories[i]['log_probs'].append(log_p)

            # Check termination
            terminated = actions == TERMINATE_ACTION
            term_global_idx = active_idx[terminated]
            done[term_global_idx] = True

            # Update states for non-terminated
            not_terminated = ~terminated
            if not_terminated.any():
                nt_idx = active_idx[not_terminated]
                nt_actions = actions[not_terminated]
                s[nt_idx] = self.env.update(s[nt_idx], nt_actions)

            step += 1

        # Force-terminate remaining (hit T_MAX)
        still_active = ~done
        if still_active.any():
            for i in still_active.nonzero(as_tuple=True)[0]:
                idx = i.item()
                # Don't add terminate to trajectory — just stop

        # Finalize trajectory info
        for t in trajectories:
            t['length'] = len(t['actions'])
            t['unique_states'] = len(t['state_set'])
            del t['state_set']

        return trajectories

    def compute_loss(self, trajectories: list) -> torch.Tensor:
        """Compute REINFORCE-style loss with baseline and length normalization.

        Changed: added moving-average baseline and per-step normalization
        Why: raw REINFORCE has high variance causing loss oscillation;
             baseline reduces variance, length normalization stabilizes gradients

        L(θ) = mean over batch of: -(R(τ) - baseline) · (1/T) · Σ log π_θ(a_t | s_t)
        """
        # Compute rewards
        traj_info = [{'length': t['length'], 'unique_states': t['unique_states']}
                     for t in trajectories]
        rewards = self.env.reward(traj_info)

        # Moving average baseline (reduces REINFORCE variance)
        reward_mean = rewards.mean().item()
        if not hasattr(self, '_reward_baseline'):
            self._reward_baseline = reward_mean
        else:
            self._reward_baseline = 0.9 * self._reward_baseline + 0.1 * reward_mean

        losses = []
        for i, t in enumerate(trajectories):
            if t['length'] == 0:
                continue
            log_prob_sum = sum(t['log_probs'])
            # Subtract baseline and normalize by trajectory length
            advantage = rewards[i] - self._reward_baseline
            loss_i = -advantage * log_prob_sum / t['length']
            losses.append(loss_i)

        if not losses:
            return torch.tensor(0.0, requires_grad=True)

        return torch.stack(losses).mean()


# ── Training Loop ──

def train(batch_size: int = 256, num_epochs: int = 1000, lr: float = 5e-3,
          hidden_dim: int = 64, epsilon: float = 0.1,
          device: str = "cpu", save_dir: str = None) -> OpalGFlowNet:
    """Train GFlowNet policy on Opal FSM.

    Args:
        batch_size: trajectories per training step
        num_epochs: training iterations
        lr: learning rate
        hidden_dim: policy hidden layer size
        epsilon: ε-greedy exploration rate
        device: 'cpu' or 'mps'
        save_dir: where to save trained model

    Returns:
        Trained OpalGFlowNet
    """
    env = OpalFSMEnvironment()
    policy = ForwardPolicy(env.state_dim, hidden_dim, env.num_actions)
    model = OpalGFlowNet(policy, env, epsilon=epsilon)
    optimizer = Adam(model.parameters(), lr=lr)

    print(f"Training GFlowNet: state_dim={env.state_dim}, actions={env.num_actions}")
    print(f"  batch_size={batch_size}, epochs={num_epochs}, lr={lr}, ε={epsilon}")
    print(f"  hidden_dim={hidden_dim}, device={device}")
    print(f"  FSM: {NUM_STATES} states, {len(DELTA)} transitions")
    print()

    best_loss = float('inf')
    loss_history = []

    for epoch in range(num_epochs):
        optimizer.zero_grad()

        # Sample trajectories
        trajectories = model.sample_trajectories(batch_size)

        # Compute loss
        loss = model.compute_loss(trajectories)
        loss.backward()
        optimizer.step()

        loss_val = loss.item()
        loss_history.append(loss_val)

        # Stats
        lengths = [t['length'] for t in trajectories]
        unique_states = [t['unique_states'] for t in trajectories]
        avg_len = sum(lengths) / len(lengths)
        avg_unique = sum(unique_states) / len(unique_states)
        max_len = max(lengths)

        if epoch % 50 == 0 or epoch == num_epochs - 1:
            print(f"  epoch {epoch:4d} | loss={loss_val:8.4f} | "
                  f"avg_len={avg_len:5.1f} | max_len={max_len:3d} | "
                  f"avg_unique_states={avg_unique:.1f}")

        if loss_val < best_loss:
            best_loss = loss_val

    print(f"\nTraining complete. Best loss: {best_loss:.4f}")

    # Save model
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        model_path = os.path.join(save_dir, "gflownet_policy.pt")
        torch.save({
            'policy_state_dict': policy.state_dict(),
            'epsilon': epsilon,
            'hidden_dim': hidden_dim,
            'state_dim': env.state_dim,
            'num_actions': env.num_actions,
            'loss_history': loss_history,
        }, model_path)
        print(f"Model saved to {model_path}")

    return model


# ── Generation ──

def generate_trajectories(model: OpalGFlowNet, n_trajectories: int,
                          epsilon: float = 0.0) -> list:
    """Generate trajectories using trained policy.

    Args:
        model: trained GFlowNet
        n_trajectories: how many to generate
        epsilon: exploration rate during generation (0 = greedy)

    Returns:
        list of trajectory dicts with FSM state/action sequences
    """
    old_eps = model.epsilon
    model.epsilon = epsilon

    all_trajectories = []
    remaining = n_trajectories
    batch_size = min(512, n_trajectories)

    while remaining > 0:
        bs = min(batch_size, remaining)
        trajectories = model.sample_trajectories(bs)

        for t in trajectories:
            # Convert to FSM state/action pairs
            fsm_trajectory = []
            for j, (state_tensor, action_idx) in enumerate(zip(t['states'], t['actions'])):
                if action_idx == TERMINATE_ACTION:
                    break
                state_idx = state_tensor[:NUM_STATES].argmax().item()
                fsm_state = IDX_TO_STATE[state_idx]
                fsm_action = IDX_TO_ACTION.get(action_idx)
                if fsm_action is None:
                    break

                # Get transition info from FSM
                transition = DELTA.get((fsm_state, fsm_action))
                if transition is None:
                    break

                fsm_trajectory.append({
                    'state': fsm_state,
                    'action': fsm_action,
                    'next_state': transition.next_state,
                    'expected_status': transition.expected_status,
                    'rules': transition.rules,
                    'description': transition.description,
                })

            if len(fsm_trajectory) > 0:
                all_trajectories.append(fsm_trajectory)

        remaining -= bs

    model.epsilon = old_eps
    return all_trajectories[:n_trajectories]


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="Train Opal GFlowNet")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=1000)
    parser.add_argument("--lr", type=float, default=5e-3)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--epsilon", type=float, default=0.1)
    parser.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    parser.add_argument("--save-dir", default="runs/gflownet")
    parser.add_argument("--generate", type=int, default=0,
                        help="After training, generate N trajectories")
    args = parser.parse_args()

    model = train(
        batch_size=args.batch_size,
        num_epochs=args.epochs,
        lr=args.lr,
        hidden_dim=args.hidden_dim,
        epsilon=args.epsilon,
        device=args.device,
        save_dir=args.save_dir,
    )

    if args.generate > 0:
        print(f"\nGenerating {args.generate} trajectories...")
        trajectories = generate_trajectories(model, args.generate, epsilon=0.05)
        print(f"Generated {len(trajectories)} trajectories")

        # Stats
        lengths = [len(t) for t in trajectories]
        from collections import Counter
        action_counts = Counter()
        state_counts = Counter()
        for t in trajectories:
            for step in t:
                action_counts[step['action'].name] += 1
                state_counts[step['state'].name] += 1

        print(f"  Length: min={min(lengths)}, max={max(lengths)}, "
              f"avg={sum(lengths)/len(lengths):.1f}")
        print(f"  Unique action types used: {len(action_counts)}")
        print(f"  Unique states visited: {len(state_counts)}")
        print(f"  Top 5 actions: {action_counts.most_common(5)}")

        # Save raw trajectories
        out_path = os.path.join(args.save_dir, "raw_trajectories.json")
        serializable = []
        for t in trajectories:
            serializable.append([{
                'state': step['state'].name,
                'action': step['action'].name,
                'next_state': step['next_state'].name,
                'expected_status': step['expected_status'],
                'rules': list(step['rules']),
            } for step in t])

        with open(out_path, 'w') as f:
            json.dump(serializable, f, indent=2)
        print(f"  Raw trajectories saved to {out_path}")


if __name__ == "__main__":
    main()
