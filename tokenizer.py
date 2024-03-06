from typing import Any

from transformers import AutoTokenizer

# i am lazy with typcasting
def load_tokenizer(model_path: str) -> Any:
    return AutoTokenizer.from_pretrained(model_path)
