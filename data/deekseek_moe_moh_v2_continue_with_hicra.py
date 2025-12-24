# Import statements
import torch
import torch.nn as nn
from torch.nn import functional as F
from typing import Optional, Tuple, Dict
import time
import tiktoken
import os
import math
import pickle
from cosmopedia_loader import CosmopediaMultiSplitLoader
from tqdm import tqdm
import logging
import glob
import psutil, gc
proc = psutil.Process(os.getpid())

def mem_gb():
    return proc.memory_info().rss / (1024**3)

    # add near imports
import json
import hashlib
import random

# add near your config/constants (top of main() is fine)
TRACE_DIR = "trained_data_traces"
TRACE_CHUNK = 1000               # 1 json per 1000 steps
TRACE_SAMPLE_SEQS = 16            # store decoded text for N sequences per step (keep small!)
TRACE_MAX_CHARS = 512            # truncate decoded text to keep files small
TRACE_PER_SEQ_HASHES = False      # set False to only store batch hash (smaller/faster)

os.makedirs(TRACE_DIR, exist_ok=True)
enc = tiktoken.get_encoding("gpt2")

_trace_f = None
_trace_chunk_start = None
_trace_chunk_end = None

def _open_trace_for_step(step: int):
    global _trace_f, _trace_chunk_start, _trace_chunk_end
    chunk_start = ((step - 1) // TRACE_CHUNK) * TRACE_CHUNK + 1
    chunk_end = chunk_start + TRACE_CHUNK - 1
    if _trace_f is None or chunk_start != _trace_chunk_start:
        if _trace_f is not None:
            _trace_f.close()
        _trace_chunk_start, _trace_chunk_end = chunk_start, chunk_end
        path = os.path.join(TRACE_DIR, f"trace_{chunk_start:06d}_{chunk_end:06d}.jsonl")
        _trace_f = open(path, "a", encoding="utf-8")
    return _trace_f

def _hash_tensor_int(x_cpu: torch.Tensor) -> str:
    # x_cpu: 1D/2D int tensor on CPU
    # stable hash of raw bytes
    b = x_cpu.contiguous().numpy().tobytes()
    return hashlib.sha256(b).hexdigest()

def next_batch_with_meta(multi_loader):
    # replicate MultiSplitLoader sampling BUT also return split name
    split_idx = random.choices(range(len(multi_loader.loaders)), weights=multi_loader.weights)[0]
    x, y = multi_loader.loaders[split_idx].next_batch()
    split_name = multi_loader.splits[split_idx]
    return x, y, split_name

def write_trace(step: int, split_name: str, x_tokens: torch.Tensor):
    """
    x_tokens: [B, T] token ids (on any device). We only hash/store from CPU.
    Writes 1 JSON line per step into the current 1000-step trace file.
    """
    f = _open_trace_for_step(step)
    x_cpu = x_tokens.detach().to("cpu")

    # batch-level hash
    batch_hash = _hash_tensor_int(x_cpu)

    entry = {
        "step": step,
        "split": split_name,
        "B": int(x_cpu.shape[0]),
        "T": int(x_cpu.shape[1]),
        "batch_sha256": batch_hash,
    }

    if TRACE_PER_SEQ_HASHES:
        entry["seq_sha256"] = [_hash_tensor_int(x_cpu[b]) for b in range(x_cpu.shape[0])]

    # small decoded sample for sanity checking (NOT the whole batch)
    sample_n = min(TRACE_SAMPLE_SEQS, x_cpu.shape[0])
    sample_idxs = list(range(sample_n))
    entry["sample_text"] = []
    for b in sample_idxs:
        txt = enc.decode(x_cpu[b].tolist())
        entry["sample_text"].append(txt[:TRACE_MAX_CHARS])

    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    f.flush()


# ===========================
# RL (HICRA-style) HELPERS
# ===========================
# You will place JSON files like rl_dataset/50_51.json, rl_dataset/51_52.json, ...
# Each file should be a list of {"question": "...", "answer": "..."} dicts.
RL_DATA_DIR = "rl_dataset"
RL_MAX_NEW_TOKENS = 4          # one-word answer, but allow a couple tokens for BPE
RL_TEMPERATURE = 0.8
RL_TOP_K = 50
RL_TOP_P = 0.95

RL_LR = 1e-6                   # keep tiny: this is "exam consolidation", not pretraining
RL_WEIGHT_DECAY = 0.0
RL_GRAD_CLIP = 1.0
RL_BATCH_SIZE = 8              # gradient accumulation
RL_EPOCHS = 1

# HICRA weighting mode:
# - "entropy_drop": weights tokens by entropy drop between consecutive generated tokens (proxy for planning)
# - "positional": simple geometric decay (first generated token gets most credit)
HICRA_MODE = "entropy_drop"
HICRA_POS_DECAY = 0.75

def _normalize_answer(s: str) -> str:
    s = (s or "").strip().lower()
    # keep only first "word" (letters/numbers) for strict one-word answers
    # allow hyphen as part of word (optional)
    s = s.splitlines()[0].strip()
    # split on whitespace, take first token
    if not s:
        return ""
    w = s.split()[0].strip()
    # strip common punctuation
    w = w.strip(".,;:!?"'()[]{}<>")
    return w

def _safe_model_logits(model_out):
    # handle different forward return types across your scripts
    # common patterns:
    # 1) logits
    # 2) (logits,)
    # 3) (loss, logits)
    if isinstance(model_out, torch.Tensor):
        return model_out
    if isinstance(model_out, (tuple, list)):
        if len(model_out) == 0:
            raise RuntimeError("Model output tuple/list is empty")
        # prefer last element as logits if first is loss
        if isinstance(model_out[-1], torch.Tensor):
            return model_out[-1]
    # huggingface-style: object with .logits
    if hasattr(model_out, "logits"):
        return model_out.logits
    raise RuntimeError(f"Cannot extract logits from model output type: {type(model_out)}")

@torch.no_grad()
def _generate_one_word(model, enc, question: str, device: str):
    # Prompt enforces one-word answer, no explanation.
    prompt = (
        "Answer in exactly one word.\n"
        "Do not add punctuation.\n\n"
        f"Question: {question.strip()}\n"
        "Answer:"
    )
    prompt_ids = enc.encode(prompt)
    input_ids = torch.tensor([prompt_ids], dtype=torch.long, device=device)

    generated = model.generate(
        input_ids,
        max_new_tokens=RL_MAX_NEW_TOKENS,
        temperature=RL_TEMPERATURE,
        top_k=RL_TOP_K,
        top_p=RL_TOP_P,
    )

    full = generated[0].tolist()
    gen_ids = full[len(prompt_ids):]
    gen_text = enc.decode(gen_ids)
    pred = _normalize_answer(gen_text)
    return prompt_ids, gen_ids, pred

def _hicra_weights_from_logits(gen_logits: torch.Tensor):
    """
    gen_logits: [G, V] logits for each generated position (teacher-forced)
    returns weights [G] summing to 1
    """
    with torch.no_grad():
        logp = F.log_softmax(gen_logits, dim=-1)          # [G, V]
        p = logp.exp()
        ent = -(p * logp).sum(dim=-1)                     # [G]
        if HICRA_MODE == "positional":
            w = torch.tensor([HICRA_POS_DECAY**i for i in range(len(ent))], device=ent.device, dtype=ent.dtype)
        else:
            # entropy_drop proxy: planning decisions tend to reduce uncertainty early
            if len(ent) == 1:
                w = torch.ones_like(ent)
            else:
                drops = ent[:-1] - ent[1:]
                drops = F.softplus(drops)                 # keep positive, smooth
                w = torch.cat([drops, drops.new_tensor([1e-4])], dim=0)  # tiny tail weight
        w = w / (w.sum() + 1e-8)
        return w

def run_hicra_rl_on_file(model, device: str, json_path: str, logger=None):
    """
    Runs a small RL "exam consolidation" phase using HICRA-style token weighting.
    Reward: 1 if predicted one-word answer matches expected (normalized), else 0.
    Updates model weights in-place and saves an RL checkpoint afterwards.
    """
    if not os.path.exists(json_path):
        if logger: logger.warning(f"[HICRA] RL dataset not found: {json_path} (skipping)")
        return

    enc = tiktoken.get_encoding("gpt2")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Build a tiny RL optimizer (separate from pretrain optimizer)
    rl_optim = torch.optim.AdamW(model.parameters(), lr=RL_LR, weight_decay=RL_WEIGHT_DECAY)
    model.train()

    # moving baseline for variance reduction
    baseline = 0.0
    beta = 0.9

    n = len(data)
    if logger:
        logger.info(f"[HICRA] Starting RL on {json_path} with {n} examples (epochs={RL_EPOCHS}, lr={RL_LR})")

    total_updates = 0
    correct = 0

    for epoch in range(RL_EPOCHS):
        random.shuffle(data)
        rl_optim.zero_grad(set_to_none=True)

        for idx, ex in enumerate(data, 1):
            q = ex.get("question", "")
            a = _normalize_answer(ex.get("answer", ""))

            # 1) sample an answer (policy rollout)
            prompt_ids, gen_ids, pred = _generate_one_word(model, enc, q, device)
            r = 1.0 if (pred == a and pred != "") else 0.0
            correct += int(r)

            # update baseline
            baseline = beta * baseline + (1 - beta) * r
            adv = r - baseline

            # 2) compute logprobs for generated tokens (teacher-forced)
            #    full sequence = prompt + generated
            full_ids = prompt_ids + gen_ids
            full = torch.tensor([full_ids], dtype=torch.long, device=device)

            out = model(input_ids=full)  # logits-only forward
            logits = _safe_model_logits(out)              # [1, S, V]
            logits = logits[0]                            # [S, V]

            G = len(gen_ids)
            if G == 0:
                continue

            # logits for each generated token come from positions right BEFORE the token
            start = len(prompt_ids) - 1
            gen_logits = logits[start:start+G, :]         # [G, V]
            gen_targets = torch.tensor(gen_ids, dtype=torch.long, device=device)  # [G]

            logp = F.log_softmax(gen_logits, dim=-1)
            token_logp = logp.gather(dim=-1, index=gen_targets.unsqueeze(-1)).squeeze(-1)  # [G]

            # 3) HICRA weights
            w = _hicra_weights_from_logits(gen_logits)    # [G]

            # 4) policy gradient loss (negative because we minimize)
            #    loss = -adv * sum_t w_t * log pi(a_t | s_t)
            loss = -(adv * (w * token_logp).sum())

            loss.backward()

            # update every RL_BATCH_SIZE examples (grad accumulation)
            if (idx % RL_BATCH_SIZE) == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), RL_GRAD_CLIP)
                rl_optim.step()
                rl_optim.zero_grad(set_to_none=True)
                total_updates += 1

        # flush remaining grads
        torch.nn.utils.clip_grad_norm_(model.parameters(), RL_GRAD_CLIP)
        rl_optim.step()
        rl_optim.zero_grad(set_to_none=True)
        total_updates += 1

    acc = correct / max(1, (n * RL_EPOCHS))
    if logger:
        logger.info(f"[HICRA] RL done. one-word accuracy={acc*100:.2f}% | baseline~{baseline:.3f} | updates={total_updates}")

# Import Fourier embedding system
import sys
from true_fourier_se_decoder import PFConfig, PFCodec, HybridEmbeddingTorch

# Import all model components - we need to import from the original file
# Since we can't easily import classes from a script, we'll define them here
# But actually, let's just import the file as a module
import importlib.util
spec = importlib.util.spec_from_file_location("deekseek_moe_moh_v2", "deekseek_moe_moh_v2.py")
deekseek_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deekseek_module)

# Now we can use the classes from the module
RMSNorm = deekseek_module.RMSNorm
LlamaRotaryEmbedding = deekseek_module.LlamaRotaryEmbedding
apply_rope = deekseek_module.apply_rope
MultiHeadLatentAttention = deekseek_module.MultiHeadLatentAttention
DeepSeekExpertLayer = deekseek_module.DeepSeekExpertLayer
DeepSeekMoE = deekseek_module.DeepSeekMoE
LlamaDecoderLayer = deekseek_module.LlamaDecoderLayer
DeepSeekConfig = deekseek_module.DeepSeekConfig
DeepSeekModel = deekseek_module.DeepSeekModel
DeepSeekForCausalLM = deekseek_module.DeepSeekForCausalLM
discover_chars_from_tiktoken = deekseek_module.discover_chars_from_tiktoken
pad_char_vocab_128 = deekseek_module.pad_char_vocab_128
create_tiktoken_vocab = deekseek_module.create_tiktoken_vocab
count_parameters = deekseek_module.count_parameters

def main():
    """Continue training from step 10000 for 20000 more steps with different data splits"""
    
    print("=" * 60)
    print("DEEPSEEK MOE + FOURIER EMBEDDINGS - CONTINUED TRAINING")
    print("Continuing from step 10000 for 20000 more steps")
    print("=" * 60)
    
    # ========== DEVICE SETUP ==========
    device = 'cpu'
    if torch.cuda.is_available():
        device = 'cuda'
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    print(f"using device: {device}")
    
    # ========== OPTIMIZATION SETTINGS ==========
    torch.set_float32_matmul_precision('high')
    
    # Set seed for reproducibility
    torch.manual_seed(1337)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(1337)
    elif device == 'mps':
        generator = torch.Generator(device='mps')
        generator.manual_seed(1337)
    
    # ========== FOURIER CODEC SETUP ==========
    print("\n" + "=" * 60)
    print("Setting up Fourier tokenizer system...")
    print("=" * 60)
    
    vocab_size = 50257  # tiktoken gpt2
    
    # Discover characters and create codec
    chars, char_to_id = discover_chars_from_tiktoken(vocab_size)
    chars128, char_to_id = pad_char_vocab_128(chars)
    
    # Create PF codec
    pf_cfg = PFConfig(
        char_vocab=chars128, 
        char_to_id=char_to_id, 
        CHAR_DIM=128, 
        POS_DIM=16, 
        D=2048, 
        length_normalize=True, 
        truncate_long_words=True
    )
    pf_codec = PFCodec(pf_cfg)
    
    # Create BPE vocabulary strings
    bpe_vocab = create_tiktoken_vocab(vocab_size)
    
    print("=" * 60)
    print("✅ Fourier codec ready!")
    print("=" * 60 + "\n")
    
    # ========== CHECKPOINT LOADING (FIRST - to get config) ==========
    CKPT_DIR = 'checkpoints'
    LOG_FILE = 'deekseek_moe_moh_v2_training.log'
    os.makedirs(CKPT_DIR, exist_ok=True)

    # Look for latest checkpoint (same logic as original training script)
    checkpoint_files = glob.glob(os.path.join(CKPT_DIR, 'model_step_*.pt'))
    start_step = 0
    checkpoint_path = None
    
    if checkpoint_files:
        # Filter to only valid checkpoint files and extract step numbers safely
        valid_checkpoints = []
        for ckpt_file in checkpoint_files:
            try:
                # Extract step number from filename like "model_step_1000.pt"
                step_str = os.path.basename(ckpt_file).split('_')[-1].split('.')[0]
                step_num = int(step_str)
                valid_checkpoints.append((step_num, ckpt_file))
            except (ValueError, IndexError):
                # Skip files that don't match the expected pattern
                continue
        
        if valid_checkpoints:
            # Sort by step number and get the latest
            valid_checkpoints.sort(key=lambda x: x[0])
            start_step, checkpoint_path = valid_checkpoints[-1]
            print(f"\n📦 Found latest checkpoint: {checkpoint_path} (step {start_step})")
        else:
            raise RuntimeError("No valid checkpoints found in checkpoints directory!")
    else:
        raise RuntimeError("No checkpoints found! Cannot continue training without a checkpoint.")
    
    print(f"📦 Loading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # ========== MODEL CONFIGURATION ==========
    # Use config from checkpoint to avoid pickling issues
    if 'config' in checkpoint:
        config = checkpoint['config']
        print(f"✅ Loaded config from checkpoint")
    elif 'config_dict' in checkpoint:
        # Reconstruct config from dict
        print("⚠️  Config saved as dict, reconstructing config object")
        config_dict = checkpoint['config_dict']
        config = DeepSeekConfig(**config_dict)
    else:
        # Fallback: create config (shouldn't happen, but just in case)
        print("⚠️  No config in checkpoint, creating new config")
        config = DeepSeekConfig(
            vocab_size=50257,
            hidden_size=768,
            num_hidden_layers=8,
            num_attention_heads=12,
            intermediate_size=512,
            num_experts=8,
            num_shared_experts=1,
            top_k_experts=2,
            compression_ratio=8,
            max_position_embeddings=2048,
            rope_theta=10000.0,
            tie_word_embeddings=False,
        )

    # ========== MODEL SETUP ==========
    K = config.hidden_size * 2
    model = DeepSeekForCausalLM(config, bpe_vocab=bpe_vocab, pf_codec=pf_codec, K=K)
    model.to(device)

    total_params, trainable_params = count_parameters(model)
    print(f"\nDeepSeek-V3 Model initialized")
    print(f"Total parameters: {total_params:,} ({total_params/1e6:.1f}M)")
    print(f"Trainable parameters: {trainable_params:,}")

    if device == 'cuda':
        try:
            model = torch.compile(model, mode='reduce-overhead')
            print("torch.compile enabled with reduce-overhead mode (CUDA)")
        except Exception as e:
            print(f"torch.compile not available: {e}")
    else:
        print("torch.compile disabled for MPS")
    
    # Load model weights
    try:
        model.load_state_dict(checkpoint['model_state_dict'])
        print(f"✅ Loaded model from step {start_step}")
        print(f"   Loss at checkpoint: {checkpoint['loss']:.4f}")
    except Exception as e:
        print(f"⚠️  Failed to load checkpoint: {e}")
        raise RuntimeError(f"Cannot continue without checkpoint from step {start_step}!")
    
    # ========== DATA LOADER ==========
    # Use multiple splits EXCLUDING stories
    print("\n" + "=" * 60)
    print("Setting up data loader with multiple splits (excluding stories)...")
    print("=" * 60)
    
    train_loader = CosmopediaMultiSplitLoader(
        B=16,
        T=512,
        splits=["web_samples_v1", "web_samples_v2", "stanford", "openstax", "khanacademy", "wikihow", "auto_math_text"],
        weights=[0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.10],  # Equal weights mostly, slightly less math
        shuffle_buffer_size=10000  # Larger buffer for better shuffling
    )
    print(f"Using Cosmopedia multi-split loader with {len(train_loader.splits)} splits")
    print(f"Splits: {', '.join(train_loader.splits)}")
    
    # ========== OPTIMIZER & LEARNING RATE SCHEDULER ==========
    # Original 10k-30k schedule: cosine decay from 3e-5 (step 10k) to 1e-5 (step 30k)
    original_start_step = 10000
    original_end_step = 30000
    original_initial_lr = 3e-5  # LR at step 10k
    original_final_lr = 1e-5    # LR at step 30k
    original_schedule_steps = original_end_step - original_start_step  # 20000 steps
    
    # If continuing past 30k, use a new schedule from 30k to 60k
    if start_step >= original_end_step:
        # Continue from 30k: gentle cosine decay from 1e-5 to 5e-6 over 30k steps
        continue_start_step = original_end_step
        continue_end_step = 60000
        continue_initial_lr = original_final_lr  # 1e-5 at step 30k
        continue_final_lr = 5e-6  # Target LR at step 60k
        continue_schedule_steps = continue_end_step - continue_start_step  # 30000 steps
        
        # Calculate LR at current step from continue schedule
        if start_step >= continue_end_step:
            initial_lr = continue_final_lr
        else:
            progress = (start_step - continue_start_step) / continue_schedule_steps
            progress = max(0.0, min(progress, 1.0))
            cosine_decay = 0.5 * (1 + math.cos(math.pi * progress))
            lr_ratio = continue_final_lr / continue_initial_lr
            initial_lr = continue_initial_lr * (lr_ratio + (1 - lr_ratio) * cosine_decay)
        
        final_lr = continue_final_lr
        target_steps = continue_end_step
        continue_steps = target_steps - start_step
        use_continue_schedule = True
    else:
        # Still in original 10k-30k schedule
        if start_step <= original_start_step:
            initial_lr = original_initial_lr
        else:
            progress = (start_step - original_start_step) / original_schedule_steps
            progress = max(0.0, min(progress, 1.0))
            cosine_decay = 0.5 * (1 + math.cos(math.pi * progress))
            lr_ratio = original_final_lr / original_initial_lr
            initial_lr = original_initial_lr * (lr_ratio + (1 - lr_ratio) * cosine_decay)
        
        final_lr = original_final_lr
        target_steps = original_end_step
        continue_steps = target_steps - start_step
        use_continue_schedule = False
    
    # CRITICAL: LambdaLR multiplies optimizer's base_lr by lambda ratio
    # So we need base_lr = schedule's initial LR, then lambda scales it
    if use_continue_schedule:
        # For 30k-60k: base should be 1e-5 (continue_initial_lr)
        optimizer_base_lr = continue_initial_lr
    else:
        # For 10k-30k: base should be 3e-5 (original_initial_lr)
        optimizer_base_lr = original_initial_lr
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=optimizer_base_lr, weight_decay=0.1)
    print(f"✅ Created optimizer with base LR = {optimizer_base_lr:.2e}")
    
    # Load optimizer state if available
    if 'optimizer_state_dict' in checkpoint:
        try:
            optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            print(f"✅ Loaded optimizer state")
            # CRITICAL: Override LR with schedule's base LR (not initial_lr at current step!)
            # The scheduler will scale this base LR according to the schedule
            for param_group in optimizer.param_groups:
                param_group['lr'] = optimizer_base_lr
            print(f"   Forced base LR to {optimizer_base_lr:.2e} (schedule's initial LR)")
        except Exception as e:
            print(f"⚠️  Could not load optimizer state: {e}")
            print("   Starting optimizer from schedule base LR")
    
    # Cosine annealing - follows original 10k-30k schedule, then continues 30k-60k if needed
    # Lambda returns a ratio that multiplies the optimizer's base_lr
    def get_lr_lambda(step):
        current_step = step + 1
        
        if use_continue_schedule:
            # Continue schedule: 30k-60k
            if current_step <= continue_start_step:
                progress = 0.0
            elif current_step >= continue_end_step:
                progress = 1.0
            else:
                progress = (current_step - continue_start_step) / continue_schedule_steps
                progress = max(0.0, min(progress, 1.0))
            
            cosine_decay = 0.5 * (1 + math.cos(math.pi * progress))
            lr_ratio = continue_final_lr / continue_initial_lr  # e.g., 5e-6 / 1e-5 = 0.5
            current_lr_ratio = lr_ratio + (1 - lr_ratio) * cosine_decay
        else:
            # Original schedule: 10k-30k
            if current_step <= original_start_step:
                progress = 0.0
            elif current_step >= original_end_step:
                progress = 1.0
            else:
                progress = (current_step - original_start_step) / original_schedule_steps
                progress = max(0.0, min(progress, 1.0))
            
            cosine_decay = 0.5 * (1 + math.cos(math.pi * progress))
            lr_ratio = original_final_lr / original_initial_lr  # e.g., 1e-5 / 3e-5 = 0.333
            current_lr_ratio = lr_ratio + (1 - lr_ratio) * cosine_decay
        
        return current_lr_ratio
    
    # CRITICAL: Verify and FORCE optimizer base LR is correct before creating scheduler
    # LambdaLR multiplies optimizer's current LR by lambda ratio, so base LR must be correct
    actual_base_lr = optimizer.param_groups[0]['lr']
    print(f"\n🔍 Pre-scheduler creation check:")
    print(f"   Optimizer actual LR: {actual_base_lr:.2e}")
    print(f"   Expected base LR: {optimizer_base_lr:.2e}")
    
    if abs(actual_base_lr - optimizer_base_lr) > 1e-7:
        print(f"   ⚠️  Optimizer base LR is WRONG! Forcing to {optimizer_base_lr:.2e}")
        for param_group in optimizer.param_groups:
            param_group['lr'] = optimizer_base_lr
        print(f"   ✅ Optimizer base LR forced to {optimizer_base_lr:.2e}")
    else:
        print(f"   ✅ Optimizer base LR is correct")
    
    # Double-check after forcing
    final_check_lr = optimizer.param_groups[0]['lr']
    if abs(final_check_lr - optimizer_base_lr) > 1e-7:
        raise RuntimeError(f"Failed to set optimizer base LR! Still {final_check_lr:.2e}, expected {optimizer_base_lr:.2e}")
    
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=get_lr_lambda)
    print(f"✅ Created scheduler with optimizer base LR = {optimizer_base_lr:.2e}")
    
    # Don't load scheduler state - we'll reinitialize to ensure correct schedule
    print(f"   Reinitializing scheduler for correct schedule (ignoring checkpoint scheduler state)")
    
    # Initialize scheduler to the correct position
    # LambdaLR's last_epoch starts at -1, and step() increments it
    # After stepping start_step times, last_epoch = start_step - 1
    # Then get_lr_lambda(start_step - 1) calculates for current_step = start_step
    print(f"   Stepping scheduler {start_step} times to reach step {start_step}...")
    for _ in range(start_step):
        scheduler.step()
    
    # Verify the LR is correct after initialization
    current_lr_after_init = scheduler.get_last_lr()[0]
    expected_lambda = get_lr_lambda(scheduler.last_epoch)
    expected_lr = optimizer_base_lr * expected_lambda
    print(f"   Scheduler initialized:")
    print(f"     - last_epoch = {scheduler.last_epoch}")
    print(f"     - lambda({scheduler.last_epoch}) = {expected_lambda:.6f}")
    print(f"     - base_lr = {optimizer_base_lr:.2e}")
    print(f"     - calculated LR = {expected_lr:.2e}")
    print(f"     - actual LR = {current_lr_after_init:.2e}")
    print(f"     - expected LR at step {start_step} = {initial_lr:.2e}")
    
    if abs(current_lr_after_init - initial_lr) > 1e-6:
        print(f"   ⚠️  LR mismatch! Forcing correct LR...")
        # Force the exact LR we want
        for param_group in optimizer.param_groups:
            param_group['lr'] = initial_lr
        print(f"   ✅ LR forced to {initial_lr:.2e}")
        # Note: This will be overridden by scheduler on next step, but at least first step is correct
    
    print(f"\nTraining Configuration:")
    print(f"  Continuing from step: {start_step}")
    print(f"  Training for: {continue_steps:,} more steps")
    print(f"  Target step: {target_steps:,}")
    print(f"  Batch size: {train_loader.B}, Seq length: {train_loader.T}")
    print(f"  Tokens per step: {train_loader.B * train_loader.T:,}")
    print(f"  Total tokens: {continue_steps * train_loader.B * train_loader.T / 1e6:.2f}M")
    if use_continue_schedule:
        print(f"\nLearning rate schedule (CONTINUE 30k-60k schedule):")
        print(f"  LR at step {start_step}: {initial_lr:.2e}")
        print(f"  LR at step {target_steps}: {final_lr:.2e}")
        print(f"  Cosine decay from step {continue_start_step} to {continue_end_step}")
    else:
        print(f"\nLearning rate schedule (ORIGINAL 10k-30k schedule):")
        print(f"  LR at step {start_step}: {initial_lr:.2e} (calculated from original schedule)")
        print(f"  LR at step {target_steps}: {final_lr:.2e} (original target)")
        print(f"  Following cosine decay from step {original_start_step} to {original_end_step}")
    
    # ========== PREDICTION FUNCTION ==========
    def sample_cosmo_prompts(loader, n=5, max_words=10):
        """Sample prompts from any of the loaders in the multi-split loader"""
        prompts = []
        import random
        for _ in range(n):
            try:
                # Pick a random loader from the multi-split loader
                random_loader = random.choice(loader.loaders)
                text = random_loader._get_next_text()
                words = text.strip().split()
                if not words:
                    continue
                keep = min(len(words), max_words)
                prompts.append(" ".join(words[:keep]))
            except Exception:
                continue
        return prompts
    
    def generate_prediction(model, prompt="The", max_new_tokens=50, device='cpu'):
        """Generate text prediction using the model"""
        model.eval()
        
        enc = tiktoken.get_encoding('gpt2')
        prompt_tokens = enc.encode(prompt)
        input_ids = torch.tensor([prompt_tokens], dtype=torch.long).to(device)
        
        with torch.no_grad():
            generated = model.generate(
                input_ids,
                max_new_tokens=max_new_tokens,
                temperature=0.8,
                top_k=50,
                top_p=0.95,
            )
        
        generated_tokens = generated[0].cpu().tolist()
        generated_text = enc.decode(generated_tokens)
        
        model.train()
        return generated_text

    # ========== SETUP LOGGING ==========
    # Always append to the same log file
    log_mode = 'a'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, mode=log_mode),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger()
    
    logger.info("=" * 60)
    logger.info(f"=== CONTINUING TRAINING FROM STEP {start_step} ===")
    logger.info(f"Training for {continue_steps:,} more steps (to step {target_steps:,})")
    logger.info(f"Using splits: {', '.join(train_loader.splits)}")
    logger.info("=" * 60)
    
    # ========== TRAINING LOOP ==========
    print("\nStarting continued training...")
    print("=" * 60)
    
    # CRITICAL: Final LR check and force before training starts
    actual_lr_before_training = optimizer.param_groups[0]['lr']
    scheduler_lr_before_training = scheduler.get_last_lr()[0]
    print(f"\n🔍 Final pre-training LR verification:")
    print(f"   Optimizer LR: {actual_lr_before_training:.2e}")
    print(f"   Scheduler LR: {scheduler_lr_before_training:.2e}")
    print(f"   Expected LR at step {start_step}: {initial_lr:.2e}")
    print(f"   Optimizer base LR: {optimizer_base_lr:.2e}")
    print(f"   Scheduler last_epoch: {scheduler.last_epoch}")
    
    # Calculate what the lambda should return
    test_lambda_val = get_lr_lambda(scheduler.last_epoch)
    expected_from_lambda = optimizer_base_lr * test_lambda_val
    print(f"   Lambda({scheduler.last_epoch}) = {test_lambda_val:.6f}")
    print(f"   Expected LR = {optimizer_base_lr:.2e} × {test_lambda_val:.6f} = {expected_from_lambda:.2e}")
    
    # ALWAYS force the correct LR - don't trust scheduler if it's wrong
    if abs(actual_lr_before_training - initial_lr) > 1e-6:
        print(f"\n   ⚠️  CRITICAL: LR MISMATCH! Forcing correct LR...")
        for param_group in optimizer.param_groups:
            param_group['lr'] = initial_lr
        print(f"   ✅ Optimizer LR forced to {initial_lr:.2e}")
    else:
        print(f"   ✅ LR is correct!")
    
    # Track last loss value for final checkpoint
    last_loss_value = None
    
    for i in range(start_step, target_steps):
        current_step = i + 1
        t0 = time.time()
        
        # Get batch
        x, y, split_name = next_batch_with_meta(train_loader)

        # write trace before moving to device (cheaper)
        write_trace(current_step, split_name, x)
        if device == 'cuda':
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        else:
            x, y = x.to(device), y.to(device)
        
        # Zero gradients
        optimizer.zero_grad(set_to_none=True)
        
        # Forward pass with mixed precision
        autocast_dtype = torch.bfloat16 if device != 'cpu' else torch.bfloat16
        with torch.autocast(device_type=device if device != 'cpu' else 'cpu', dtype=autocast_dtype):
            loss, _ = model(input_ids=x, labels=y)
        
        # Backward pass
        loss.backward()
        
        # Optimizer step
        optimizer.step()
        
        # Update learning rate
        # Calculate LR directly from schedule (more reliable than trusting scheduler)
        if use_continue_schedule:
            # Continue schedule: 30k-60k
            if current_step <= continue_start_step:
                progress = 0.0
            elif current_step >= continue_end_step:
                progress = 1.0
            else:
                progress = (current_step - continue_start_step) / continue_schedule_steps
                progress = max(0.0, min(progress, 1.0))
            
            cosine_decay = 0.5 * (1 + math.cos(math.pi * progress))
            lr_ratio = continue_final_lr / continue_initial_lr
            current_lr_ratio = lr_ratio + (1 - lr_ratio) * cosine_decay
            current_lr = continue_initial_lr * current_lr_ratio
        else:
            # Original schedule: 10k-30k
            if current_step <= original_start_step:
                progress = 0.0
            elif current_step >= original_end_step:
                progress = 1.0
            else:
                progress = (current_step - original_start_step) / original_schedule_steps
                progress = max(0.0, min(progress, 1.0))
            
            cosine_decay = 0.5 * (1 + math.cos(math.pi * progress))
            lr_ratio = original_final_lr / original_initial_lr
            current_lr_ratio = lr_ratio + (1 - lr_ratio) * cosine_decay
            current_lr = original_initial_lr * current_lr_ratio
        
        # Set LR directly (bypass scheduler to ensure correctness)
        for param_group in optimizer.param_groups:
            param_group['lr'] = current_lr
        
        # Still step scheduler to keep it in sync (for checkpoint saving)
        scheduler.step()
        
        # Update load balancing periodically
        if current_step % 10 == 0:
            model.update_expert_load_balancing(x)
            model.update_attention_head_load_balancing()
            # Explicit cleanup
            if device == 'cuda':
                torch.cuda.empty_cache()
            if device == "mps":
                try:
                    torch.mps.empty_cache()
                except Exception:
                    pass
            gc.collect()
            logger.info(f"[MEM] rss={mem_gb():.2f} GB")
        
        # Synchronize for accurate timing
        if device == 'cuda':
            torch.cuda.synchronize()
        elif device == 'mps':
            pass
        
        # Timing and metrics
        t1 = time.time()
        dt = (t1 - t0) * 1000  # milliseconds
        tokens_per_sec = (train_loader.B * train_loader.T) / (t1 - t0)
        
        # Log to both console and file
        loss_value = loss.item()
        last_loss_value = loss_value
        log_msg = f'step {current_step:4d} | loss: {loss_value:.4f} | lr: {current_lr:.2e} | dt: {dt:6.2f}ms | tok/sec: {tokens_per_sec:8.2f}'
        logger.info(log_msg)
        # free refs ASAP
        del loss
        del x, y
        
        # Generate predictions every 100 steps
        if current_step % 100 == 0:
            logger.info("\n" + "=" * 60)
            logger.info(f"GENERATION SAMPLES AT STEP {current_step}")
            logger.info("=" * 60)
            
            import random
            sampled = sample_cosmo_prompts(train_loader, n=5, max_words=10)
            if len(sampled) >= 3:
                selected_prompts = random.sample(sampled, 3)
            elif len(sampled) > 0:
                selected_prompts = sampled
            else:
                selected_prompts = [
                    "In the heart of",
                    "Across the ocean",
                    "When the stars aligned",
                ]
            
            for idx, prompt in enumerate(selected_prompts, 1):
                try:
                    logger.info(f"\n[Sample {idx}/3] Prompt: '{prompt}'")
                    prediction = generate_prediction(model, prompt=prompt, max_new_tokens=50, device=device)
                    logger.info(f"[Sample {idx}/3] Generated: {prediction}")
                except Exception as e:
                    logger.error(f"[Sample {idx}/3] Generation failed: {e}")
            
            logger.info("=" * 60 + "\n")
        
        # Save model checkpoint every 1000 steps
        if current_step % 1000 == 0:
            checkpoint_path = os.path.join(CKPT_DIR, f"model_step_{current_step}.pt")
            # Save config as dict to avoid pickling issues with class instances from different modules
            try:
                config_dict = {k: v for k, v in config.__dict__.items() if not k.startswith('_')}
            except Exception as e:
                logger.warning(f"Could not extract config dict: {e}, using empty dict")
                config_dict = {}
            
            try:
                torch.save({
                    'step': current_step,
                    'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'scheduler_state_dict': scheduler.state_dict(),
                    'loss': loss_value,
                    'config_dict': config_dict,  # Save as dict to avoid pickling errors
                }, checkpoint_path)
                logger.info(f'\n[Checkpoint saved] Step {current_step} -> {checkpoint_path} (LR: {current_lr:.2e})\n')
                # ===== HICRA RL PHASE (exam consolidation) =====
                # Example: at step 51000 -> rl_dataset/50_51.json
                if current_step >= 50000:
                    k2 = current_step // 1000
                    k1 = k2 - 1
                    rl_path = os.path.join(RL_DATA_DIR, f"{k1}_{k2}.json")
                    try:
                        run_hicra_rl_on_file(model, device=device, json_path=rl_path, logger=logger)
                        rl_ckpt_path = os.path.join(CKPT_DIR, f"model_step_{current_step}_rl.pt")
                        torch.save({
                            'step': current_step,
                            'model_state_dict': model.state_dict(),
                            'loss': loss_value,
                            'rl_dataset': rl_path,
                        }, rl_ckpt_path)
                        logger.info(f"[HICRA] RL checkpoint saved -> {rl_ckpt_path}")
                    except Exception as e:
                        logger.error(f"[HICRA] RL phase failed at step {current_step} using {rl_path}: {e}")

            except Exception as e:
                # Critical: if checkpoint save fails, try saving without config_dict
                logger.error(f"⚠️  Failed to save checkpoint with config_dict: {e}")
                logger.error(f"   Attempting to save without config_dict...")
                try:
                    torch.save({
                        'step': current_step,
                        'model_state_dict': model.state_dict(),
                        'optimizer_state_dict': optimizer.state_dict(),
                        'scheduler_state_dict': scheduler.state_dict(),
                        'loss': loss_value,
                        # No config_dict - can be reconstructed from model
                    }, checkpoint_path)
                    logger.info(f'✅ [Checkpoint saved WITHOUT config] Step {current_step} -> {checkpoint_path}\n')
                    # ===== HICRA RL PHASE (exam consolidation) =====
                    # Example: at step 51000 -> rl_dataset/50_51.json
                    if current_step >= 50000:
                        k2 = current_step // 1000
                        k1 = k2 - 1
                        rl_path = os.path.join(RL_DATA_DIR, f"{k1}_{k2}.json")
                        try:
                            run_hicra_rl_on_file(model, device=device, json_path=rl_path, logger=logger)
                            rl_ckpt_path = os.path.join(CKPT_DIR, f"model_step_{current_step}_rl.pt")
                            torch.save({
                                'step': current_step,
                                'model_state_dict': model.state_dict(),
                                'loss': loss_value,
                                'rl_dataset': rl_path,
                            }, rl_ckpt_path)
                            logger.info(f"[HICRA] RL checkpoint saved -> {rl_ckpt_path}")
                        except Exception as e:
                            logger.error(f"[HICRA] RL phase failed at step {current_step} using {rl_path}: {e}")

                except Exception as e2:
                    logger.error(f"❌ CRITICAL: Failed to save checkpoint even without config: {e2}")
                    logger.error(f"   Training will continue, but checkpoint at step {current_step} was NOT saved!")
                    # Don't raise - continue training
    
    # Save final model
    final_checkpoint_path = os.path.join(CKPT_DIR, "model_final.pt")
    final_loss = last_loss_value if last_loss_value is not None else 0.0
    # Save config as dict to avoid pickling issues
    try:
        config_dict = {k: v for k, v in config.__dict__.items() if not k.startswith('_')}
    except Exception as e:
        logger.warning(f"Could not extract config dict for final checkpoint: {e}, using empty dict")
        config_dict = {}
    
    try:
        torch.save({
            'step': target_steps,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'scheduler_state_dict': scheduler.state_dict(),
            'loss': final_loss,
            'config_dict': config_dict,  # Save as dict to avoid pickling errors
        }, final_checkpoint_path)
    except Exception as e:
        # Critical: if final checkpoint save fails, try saving without config_dict
        logger.error(f"⚠️  Failed to save final checkpoint with config_dict: {e}")
        logger.error(f"   Attempting to save without config_dict...")
        try:
            torch.save({
            'step': target_steps,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scheduler_state_dict': scheduler.state_dict(),
                'loss': final_loss,
                # No config_dict - can be reconstructed from model
            }, final_checkpoint_path)
            logger.info(f'✅ Final checkpoint saved WITHOUT config')
        except Exception as e2:
            logger.error(f"❌ CRITICAL: Failed to save final checkpoint even without config: {e2}")
            raise RuntimeError(f"Could not save final checkpoint: {e2}")
    
    logger.info("=" * 60)
    logger.info(f"\nTraining completed! Final step: {target_steps}, Final loss: {final_loss:.4f}")
    logger.info(f"Final model saved to: {final_checkpoint_path}")
    
    return model, final_loss


if __name__ == "__main__":
    model, final_loss = main()

