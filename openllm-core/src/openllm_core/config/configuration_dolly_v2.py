from __future__ import annotations
import typing as t

import openllm_core

from openllm_core._prompt import process_prompt
from openllm_core.utils import dantic

if t.TYPE_CHECKING:
  import transformers

START_DOLLY_V2_COMMAND_DOCSTRING = '''\
Run a LLMServer for dolly-v2 model.

\b
> See more information about dolly-v2 at [databricks/dolly-v2-3b](https://huggingface.co/databricks/dolly-v2-3b)

\b
## Usage

Currently, dolly-v2 only supports PyTorch. Make sure ``torch`` is available in your system.

\b
Dolly-v2 Runner will use databricks/dolly-v2-3b as the default model. To change to any other dolly-v2
saved pretrained, or a fine-tune dolly-v2, provide ``OPENLLM_DOLLY_V2_MODEL_ID='databricks/dolly-v2-7b'``
or provide `--model-id` flag when running ``openllm start dolly-v2``:

\b
$ openllm start dolly-v2 --model-id databricks/dolly-v2-7b
'''
INSTRUCTION_KEY = '### Instruction:'
RESPONSE_KEY = '### Response:'
END_KEY = '### End'
INTRO_BLURB = 'Below is an instruction that describes a task. Write a response that appropriately completes the request.'
# NOTE: This is the prompt that is used for generating responses using an already
# trained model.  It ends with the response key, where the job of the model is to provide
# the completion that follows it (i.e. the response itself).
DEFAULT_PROMPT_TEMPLATE = '''{intro}
{instruction_key}
{instruction}
{response_key}
'''.format(intro=INTRO_BLURB, instruction_key=INSTRUCTION_KEY, instruction='{instruction}', response_key=RESPONSE_KEY)

def get_special_token_id(tokenizer: transformers.PreTrainedTokenizer, key: str) -> int:
  '''Gets the token ID for a given string that has been added to the tokenizer as a special token.

  When training, we configure the tokenizer so that the sequences like "### Instruction:" and "### End" are
  treated specially and converted to a single, new token.  This retrieves the token ID each of these keys map to.

  Args:
    tokenizer: the tokenizer
    key: the key to convert to a single token

  Raises:
    RuntimeError: if more than one ID was generated

  Returns:
    int: the token ID for the given key.
  '''
  token_ids = tokenizer.encode(key)
  if len(token_ids) > 1: raise ValueError(f"Expected only a single token for '{key}' but found {token_ids}")
  return token_ids[0]

class DollyV2Config(openllm_core.LLMConfig):
  """Databricks` Dolly is an instruction-following large language model trained on the Databricks machine learning platform that is licensed for commercial use.

  Based on pythia-12b, Dolly is trained on ~15k instruction/response fine tuning records databricks-dolly-15k
  generated by Databricks employees in capability domains from the InstructGPT paper, including brainstorming,
  classification, closed QA, generation, information extraction, open QA and summarization.

  dolly-v2-12b is not a state-of-the-art model, but does exhibit surprisingly high quality instruction
  following behavior not characteristic of the foundation model on which it is based.

  Refer to [Databricks's Dolly page](https://github.com/databrickslabs/dolly) for more information.
  """
  __config__ = {
      'timeout': 3600000,
      'url': 'https://github.com/databrickslabs/dolly',
      'architecture': 'GPTNeoXForCausalLM',
      'default_id': 'databricks/dolly-v2-3b',
      'model_ids': ['databricks/dolly-v2-3b', 'databricks/dolly-v2-7b', 'databricks/dolly-v2-12b']
  }
  return_full_text: bool = dantic.Field(False, description='Whether to return the full prompt to the users.')

  class GenerationConfig:
    temperature: float = 0.9
    top_p: float = 0.92
    top_k: int = 5
    max_new_tokens: int = 256
    eos_token_id: int = 50277  # NOTE: from get_special_token_id(self.tokenizer, END_KEY)

  def sanitize_parameters(self,
                          prompt: str,
                          max_new_tokens: int | None = None,
                          temperature: float | None = None,
                          top_k: int | None = None,
                          top_p: float | None = None,
                          use_default_prompt_template: bool = True,
                          **attrs: t.Any) -> tuple[str, dict[str, t.Any], dict[str, t.Any]]:
    return process_prompt(prompt, DEFAULT_PROMPT_TEMPLATE, use_default_prompt_template, **attrs), {
        'max_new_tokens': max_new_tokens,
        'top_k': top_k,
        'top_p': top_p,
        'temperature': temperature,
        **attrs
    }, {}

  def postprocess_generate(self, prompt: str, generation_result: list[dict[t.Literal['generated_text'], str]],
                           **_: t.Any) -> str:
    return generation_result[0]['generated_text']
