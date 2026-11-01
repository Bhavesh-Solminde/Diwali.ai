"""Load actual author model definitions without notebook training side effects."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from einops import rearrange
import numpy as np
import torch
from torch import nn

ROOT = Path("data/orderbook_benchmark/sources")


def definitions(source, filename, namespace, keep):
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in keep]
    if {n.name for n in nodes} != set(keep):
        raise ValueError(f"Missing model definitions in {filename}")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), namespace)


def build_model(name, context=128):
    namespace = {"torch": torch, "nn": nn, "np": np, "rearrange": rearrange,
                 "cst": SimpleNamespace(DEVICE="cpu"), "device": torch.device("cpu")}
    provenance = {"name": name, "context_seconds": context, "initialization": "fresh seed; no published weights loaded"}
    if name == "TLOB":
        manifest = json.loads((ROOT / "tlob-manifest.json").read_text())
        selected = [("models/bin.py", ["BiN"]), ("models/mlplob.py", ["MLP"]),
                    ("models/tlob.py", ["ComputeQKV", "TransformerLayer", "TLOB", "sinusoidal_positional_embedding"])]
        provenance["source_revision"] = manifest["revision"]
        provenance["source_sha256"] = {}
        for file, names in selected:
            path = ROOT / "TLOB-pinned" / file
            source = path.read_bytes()
            expected = next(x["sha256"] for x in manifest["files"] if x["path"] == file)
            if hashlib.sha256(source).hexdigest() != expected:
                raise ValueError("Author source changed")
            definitions(source.decode(), str(path), namespace, names)
            provenance["source_sha256"][file] = expected
        model = namespace["TLOB"](40, 4, context, 40, 1, True, "BTC")
        # Author BiN replaces Parameters with CUDA tensors if mixing weights go negative.
        # Clamp registered scalars instead, keeping the same positive-weight math on CPU.
        def positive_mixing(module, _):
            with torch.no_grad():
                module.y1.clamp_(min=.01)
                module.y2.clamp_(min=.01)
        model.norm_layer.register_forward_pre_hook(positive_mixing)
        provenance["compatibility"] = ["Only model definitions loaded; plotting, configuration, tracking imports omitted",
            "Device fixed to CPU", "BiN mixing weights clamped >=0.01 before forward to avoid CUDA-only Parameter replacement"]
        probabilities = False
    elif name == "DeepLOB":
        path = next(ROOT.glob("DeepLOB*/jupyter_pytorch/run_train_pytorch.ipynb"))
        notebook = json.loads(path.read_text())
        code = "\n".join("".join(c["source"]) for c in notebook["cells"]
                         if c["cell_type"] == "code" and "class deeplob(" in "".join(c["source"]))
        definitions(code, str(path), namespace, ["deeplob"])
        model = namespace["deeplob"](3)
        provenance["source_sha256"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()}
        provenance["compatibility"] = ["Original notebook model class only; notebook training cells not executed",
            "Device fixed to CPU; input adds one channel axis", "Native softmax output trained using log probabilities"]
        probabilities = True
    else:
        raise ValueError("Only TLOB and original-author DeepLOB have runnable L2 model adapters")
    provenance["parameters"] = sum(p.numel() for p in model.parameters())
    return model, probabilities, provenance


def forward(model, name, x):
    return model(x[:, None] if name == "DeepLOB" else x)


def log_probabilities(output, already_probabilities):
    return output.clamp_min(1e-9).log() if already_probabilities else output.log_softmax(dim=1)
