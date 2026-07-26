
"""
reasoning_rl.py

A reinforcement-learning-based method for encouraging LLM outputs to contain
syntactically valid and sufficiently detailed reasoning ("thinking") traces.

Core idea
---------
1. `ReasoningRewardModel` inspects a raw LLM completion and scores it on:
     - whether it contains an explicit thinking/reasoning block at all
     - whether that block is syntactically well-formed (matched, non-overlapping
       tags, correct ordering)
     - whether the block is "sufficiently detailed" (long enough and broken
       into a minimum number of discrete reasoning steps)
   The result is a scalar reward in [-1, 1].

2. `ReinforceTrainer` is a lightweight policy-gradient (REINFORCE) loop that
   uses a reward signal to update a *pluggable* policy: anything that can (a)
   sample a completion for a prompt and (b) hand back the log-probability of
   the sampled tokens/action. This keeps the trainer decoupled from any
   specific LLM library (HuggingFace, custom, etc.) -- you supply a
   `PolicyInterface` implementation and this module handles the RL update.
   The trainer accepts either a `ReasoningRewardModel` (text-based scoring)
   or an arbitrary `reward_fn(prompt, completion) -> float`, so it isn't
   locked to the "thinking trace" domain.

3. `GiftCardPolicy` (ported from rf_multiclass.txt) replaces the previous
   toy `BanditPolicy`. Instead of choosing among a handful of pre-written
   completions, it's a genuine multiclass categorical policy: each title
   (the "prompt") is classified into one of 7 gift-card action classes
   (visa, box, pack, reload, bundle, gift, card). A deterministic rule-based
   teacher (`get_ground_truth_action`) supplies the label used to compute
   reward via `reward_function`, and the policy's learnable logits are
   updated with REINFORCE just like the old bandit was -- but now over a
   real multiclass action space instead of a fixed completion list.
"""

from __future__ import annotations

import re
import math
import random
import pickle
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol, Tuple
import pandas as pd

import ast
def clean_categories(t):
    arr = ast.literal_eval(t)
    if len(arr)>0:
        return arr[-1]
    else:
        return ''


# --------------------------------------------------------------------------- #
# 1. Reward model: syntactic validity + sufficiency of "thinking"
# --------------------------------------------------------------------------- #
class ACTIONS:
    CLASSES = {
            'visa': 0, 'box': 1, 'pack': 2, 'reload': 3,
            'bundle': 4, 'gift': 5, 'card': 6
        }

class ReasoningRewardModel:
    """Scores a completion for presence/validity/detail of a thinking block."""


    """
    Deterministic rule-based *teacher* for gift-card title classification.

    Given a product title, `get_ground_truth_action` returns the correct
    one of 7 classes (visa / box / pack / reload / bundle / gift / card)
    via simple keyword rules. `get_policy_distribution` exposes that as a
    one-hot categorical distribution, matching the "teacher policy" shape
    used elsewhere in this codebase.
    """

    def __init__(self):
        self.action_map = ACTIONS.CLASSES
        self.actions = list(self.action_map.keys())  # index -> label
        self.num_actions = len(self.action_map)

    def get_ground_truth_action(self, title: str) -> int:
        """Deterministic teacher policy based on keyword rules."""
        t = title.lower()

        if 'plus $' in t and ('visa' in t or 'mastercard' in t):
            label = 'visa'
        elif any(word in t for word in ['in a', 'box', 'tin', 'envelope', 'bag', 'sleeve']):
            label = 'box'
        elif any(word in t for word in ['pack of', 'pack)', 'multipack', 'multi pack']):
            label = 'pack'
        elif any(word in t for word in ['email delivery', 'reload', 'egift']):
            label = 'reload'
        elif '+' in t:
            label = 'bundle'
        elif 'gift card' in t or 'gift code' in t:
            label = 'gift'
        else:
            label = 'card'

        return self.action_map[label]

    def get_policy_distribution(self, title: str) -> List[float]:
        """One-hot distribution over the 7 action classes for `title`."""
        action_idx = self.get_ground_truth_action(title)
        probs = [0.0] * self.num_actions
        probs[action_idx] = 1.0
        return probs

    def compute_reward(self, prompt: str, completion: Optional[str] = None) -> float:
        """+1 if the predicted class matches the teacher's ground truth, else -1."""
        if completion is None:
            reward = max(self.get_policy_distribution(prompt))
            return 1.0 if reward > 0 else -1.0
        
        true_idx = self.get_ground_truth_action(prompt)
        true_label = self.actions[true_idx]
        return 1.0 if completion == true_label else -1.0

    def evaluate(self, text: str) -> dict:
        """Full diagnostic breakdown, useful for logging/debugging."""
        
        pass


# --------------------------------------------------------------------------- #
# 2. Pluggable policy interface + REINFORCE trainer
# --------------------------------------------------------------------------- #

class PolicyInterface(Protocol):
    """Anything the trainer can sample from and update.

    Implement this against your real LLM (e.g. wrap HF `generate` +
    token log-probs, or an API-based sampler with a learnable proposal
    distribution) to do real RL fine-tuning.
    """

    def sample(self, prompt: str) -> Tuple[str, float]:
        """Return (completion_text, log_prob_of_that_completion)."""
        ...

    def update(self, prompt: str, completion: str, log_prob: float,
               advantage: float, lr: float) -> None:
        """Apply a policy-gradient update using the given advantage."""
        ...


@dataclass
class ReinforceTrainer:
    """
    Minimal REINFORCE loop:
        loss = -log_prob(completion) * advantage
        advantage = reward - baseline   (baseline = running mean reward)

    Works with any PolicyInterface, so it can drive real LLM fine-tuning
    once you supply a real policy wrapper.

    """
    reward_model: Optional[ReasoningRewardModel] = None
    reward_fn: Optional[Callable[[str, str], float]] = None
    lr: float = 0.05
    baseline_momentum: float = 0.9
    _baseline: float = field(default=0.0, init=False)

    def _score(self, prompt: str, completion: str) -> float:
        if self.reward_fn is not None:
            return self.reward_fn(prompt, completion)
        if self.reward_model is not None:
            return self.reward_model.compute_reward(prompt, completion)
        raise ValueError("Either reward_model or reward_fn must be provided.")
        
    def train_step(self, policy: PolicyInterface, prompt: str) -> dict:
        completion, log_prob = policy.sample(prompt)
        reward = self._score(prompt, completion)

        advantage = reward - self._baseline
        self._baseline = (self.baseline_momentum * self._baseline
                           + (1 - self.baseline_momentum) * reward)

        policy.update(prompt, completion, log_prob, advantage, self.lr)

        return {
            "prompt": prompt,
            "completion": completion,
            "reward": reward,
            "advantage": advantage,
            "baseline": self._baseline,
        }

    def train(self, policy: PolicyInterface, prompts: List[str],
              epochs: int = 1, verbose: bool = True) -> List[dict]:
        history = []
        for epoch in range(epochs):
            for prompt in prompts:
                log = self.train_step(policy, prompt)
                log["epoch"] = epoch
                history.append(log)
                if verbose:
                    print(f"[epoch {epoch}] reward={log['reward']:+.3f} "
                          f"baseline={log['baseline']:+.3f}  "
                          f"prompt={prompt!r} -> completion={log['completion']!r}")
        return history


class GiftCardPolicy:
    """
    Learnable multiclass policy over `GiftCardPolicy`'s 7 action classes.

    This plays the same structural role the old `BanditPolicy` played
    (per-prompt learnable logits, softmax sampling, REINFORCE update) but
    the action space is now the real 7-way gift-card classification task
    instead of a hand-picked list of candidate completions:

      - `sample(title)`  -> (predicted_label: str, log_prob: float)
      - `update(...)`    -> REINFORCE / policy-gradient step on the logits

    Reward is supplied externally (see `gift_card_reward` /
    `GiftCardPolicy.get_ground_truth_action`) via `ReinforceTrainer`'s
    `reward_fn` hook, since it depends on comparing the *predicted* class
    against the title's *true* class -- not on the completion text alone.
    """

    # def __init__(self, titles: List[str], teacher: Optional[GiftCardPolicy] = None,
    def __init__(self, titles: List[str], seed: int = 0):        
        self.action_map = ACTIONS.CLASSES
        self.actions = list(self.action_map.keys())  # index -> label
        self.num_actions = len(self.action_map)

        self.logits = {title: [0.0] * self.num_actions for title in titles}
        self._rng = random.Random(seed)

    def _ensure_prompt(self, prompt: str) -> None:
        """Initialize logits for unseen titles so inference doesn't KeyError."""
        if prompt not in self.logits:
            self.logits[prompt] = [0.0] * self.num_actions

    def _softmax(self, logits: List[float]) -> List[float]:
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        s = sum(exps)
        return [e / s for e in exps]

    def sample(self, prompt: str) -> Tuple[str, float]:
        self._ensure_prompt(prompt)
        probs = self._softmax(self.logits[prompt])
        idx = self._rng.choices(range(len(probs)), weights=probs, k=1)[0]
        return self.actions[idx], math.log(probs[idx])

    def update(self, prompt: str, completion: str, log_prob: float,
               advantage: float, lr: float) -> None:
        self._ensure_prompt(prompt)
        probs = self._softmax(self.logits[prompt])
        idx = self.actions.index(completion)
        # Gradient of log softmax w.r.t. logits, scaled by advantage (REINFORCE)
        for i in range(len(self.logits[prompt])):
            grad = (1.0 if i == idx else 0.0) - probs[i]
            self.logits[prompt][i] += lr * advantage * grad


# --------------------------------------------------------------------------- #
# Demo / self-test
# --------------------------------------------------------------------------- #

if __name__ == "__main__":

    print("=== REINFORCE demo (GiftCardPolicy, multiclass) ===")
    df = pd.read_csv("data/gift_card/train_gift.csv")
    titles = df['gift_card'].tolist()

    reward_model = ReasoningRewardModel() 
    policy = GiftCardPolicy(titles)

    def gift_card_reward(prompt: str, completion: str) -> float:
        true_idx = reward_model.get_ground_truth_action(prompt)
        true_label = reward_model.actions[true_idx]
        return 1.0 if completion == true_label else -1.0

    # trainer = ReinforceTrainer(reward_fn=gift_card_reward, lr=0.5)  # no reward_model needed; reward_fn is supplied below
    trainer = ReinforceTrainer(reward_model=reward_model, lr=0.5)  # no reward_model needed; reward_fn is supplied below

    trainer.train(policy, titles, epochs=60, verbose=False)
    model_path = Path("./models/gift_card.pk")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with model_path.open("wb") as f:
        pickle.dump(reward_model, f)
    with model_path.open("rb") as f:
        reload_reward_model = pickle.load(f)
    
    policy_path = Path("./models/gift_card_policy.pk")
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    with policy_path.open("wb") as f:
        pickle.dump(policy, f)
    with policy_path.open("rb") as f:
        reload_policy = pickle.load(f)
    
    df = pd.read_csv("data/gift_card/test_gift.csv")
    titles = df['gift_card'].tolist()
    print("\nLearned vs. ground-truth class per title:")
    for title in titles:
        reload_policy._ensure_prompt(title)
        probs = reload_policy._softmax(reload_policy.logits[title])
        pred_idx = max(range(len(probs)), key=lambda i: probs[i])
        pred_label = reload_policy.actions[pred_idx]
        true_idx = reload_reward_model.get_ground_truth_action(title)
        true_label = reload_reward_model.actions[true_idx]
        match = "OK" if pred_idx == true_idx else "MISS"
        print(f"  [{match}] p={probs[pred_idx]:.3f}  pred={pred_label:8s} "
              f"true={true_label:8s}  title={title!r}")
