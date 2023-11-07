# mypy: disable-error-code="name-defined,no-redef"
from __future__ import annotations
import logging
import typing as t

import torch
import transformers

from openllm_core._typing_compat import LiteralQuantise
from openllm_core._typing_compat import overload
from openllm_core.exceptions import MissingDependencyError
from openllm_core.utils import is_autoawq_available
from openllm_core.utils import is_autogptq_available
from openllm_core.utils import is_bitsandbytes_available
from openllm_core.utils import is_optimum_supports_gptq

if t.TYPE_CHECKING:
  from openllm_core._typing_compat import DictStrAny

  from ._llm import LLM

logger = logging.getLogger(__name__)

@overload
def infer_quantisation_config(self: LLM[t.Any, t.Any], quantise: t.Literal['int8', 'int4'], **attrs: t.Any) -> tuple[transformers.BitsAndBytesConfig, DictStrAny]:
  ...

@overload
def infer_quantisation_config(self: LLM[t.Any, t.Any], quantise: t.Literal['gptq'], **attrs: t.Any) -> tuple[transformers.GPTQConfig, DictStrAny]:
  ...

@overload
def infer_quantisation_config(self: LLM[t.Any, t.Any], quantise: t.Literal['awq'], **attrs: t.Any) -> tuple[transformers.AwqConfig, DictStrAny]:
  ...

def infer_quantisation_config(self: LLM[t.Any, t.Any], quantise: LiteralQuantise,
                              **attrs: t.Any) -> tuple[transformers.BitsAndBytesConfig | transformers.GPTQConfig | transformers.AwqConfig, DictStrAny]:
  # 8 bit configuration
  int8_threshold = attrs.pop('llm_int8_threshhold', 6.0)
  int8_enable_fp32_cpu_offload = attrs.pop('llm_int8_enable_fp32_cpu_offload', False)
  int8_skip_modules: list[str] | None = attrs.pop('llm_int8_skip_modules', None)
  int8_has_fp16_weight = attrs.pop('llm_int8_has_fp16_weight', False)

  # shared arguments for gptq and awq
  bits = attrs.pop('bits', 4)
  group_size = attrs.pop('group_size', 128)

  def create_awq_config() -> transformers.AwqConfig:
    zero_point = attrs.pop('zero_point', True)
    return transformers.AwqConfig(bits=bits, group_size=group_size, zero_point=zero_point)

  def create_gptq_config() -> transformers.GPTQConfig:
    gptq_tokenizer = attrs.pop('tokenizer', self.model_id)
    gptq_dataset = attrs.pop('dataset', 'c4')
    gptq_damp_percent = attrs.pop('damp_percent', 0.1)
    gptq_desc_act = attrs.pop('desc_act', False)
    gptq_sym = attrs.pop('sym', True)
    gptq_true_sequential = attrs.pop('true_sequential', True)
    gptq_use_cuda_fp16 = attrs.pop('use_cuda_fp16', True if torch.cuda.is_available() else False)
    gptq_model_seqlen = attrs.pop('model_seqlen', None)
    gptq_block_name_to_quantize = attrs.pop('block_name_to_quantize', None)
    gptq_module_name_preceding_first_block = attrs.pop('module_name_preceding_first_block', None)
    gptq_batch_size = attrs.pop('batch_size', 1)
    gptq_pad_token_id = attrs.pop('pad_token_id', None)
    gptq_disable_exllama = attrs.pop('disable_exllama', False)
    return transformers.GPTQConfig(bits=bits,
                                   tokenizer=gptq_tokenizer,
                                   dataset=gptq_dataset,
                                   group_size=group_size,
                                   damp_percent=gptq_damp_percent,
                                   desc_act=gptq_desc_act,
                                   sym=gptq_sym,
                                   true_sequential=gptq_true_sequential,
                                   use_cuda_fp16=gptq_use_cuda_fp16,
                                   model_seqlen=gptq_model_seqlen,
                                   block_name_to_quantize=gptq_block_name_to_quantize,
                                   module_name_preceding_first_block=gptq_module_name_preceding_first_block,
                                   batch_size=gptq_batch_size,
                                   pad_token_id=gptq_pad_token_id,
                                   disable_exllama=gptq_disable_exllama)

  def create_int8_config(int8_skip_modules: list[str] | None) -> transformers.BitsAndBytesConfig:
    # if int8_skip_modules is None: int8_skip_modules = []
    # if 'lm_head' not in int8_skip_modules and self.config_class.__openllm_model_type__ == 'causal_lm':
    #   logger.debug("Skipping 'lm_head' for quantization for %s", self.__name__)
    #   int8_skip_modules.append('lm_head')
    return transformers.BitsAndBytesConfig(load_in_8bit=True,
                                           llm_int8_enable_fp32_cpu_offload=int8_enable_fp32_cpu_offload,
                                           llm_int8_threshhold=int8_threshold,
                                           llm_int8_skip_modules=int8_skip_modules,
                                           llm_int8_has_fp16_weight=int8_has_fp16_weight)

  # 4 bit configuration
  int4_compute_dtype = attrs.pop('bnb_4bit_compute_dtype', torch.bfloat16)
  int4_quant_type = attrs.pop('bnb_4bit_quant_type', 'nf4')
  int4_use_double_quant = attrs.pop('bnb_4bit_use_double_quant', True)

  # NOTE: Quantization setup quantize is a openllm.LLM feature, where we can quantize the model with bitsandbytes or quantization aware training.
  if not is_bitsandbytes_available():
    raise RuntimeError("Quantization requires bitsandbytes to be installed. Make sure to install OpenLLM with 'pip install \"openllm[fine-tune]\"'")
  if quantise == 'int8': quantisation_config = create_int8_config(int8_skip_modules)
  elif quantise == 'int4':
    quantisation_config = transformers.BitsAndBytesConfig(load_in_4bit=True,
                                                          bnb_4bit_compute_dtype=int4_compute_dtype,
                                                          bnb_4bit_quant_type=int4_quant_type,
                                                          bnb_4bit_use_double_quant=int4_use_double_quant)
  elif quantise == 'gptq':
    if not is_autogptq_available() or not is_optimum_supports_gptq():
      raise MissingDependencyError(
          "'quantize=\"gptq\"' requires 'auto-gptq' and 'optimum>=0.12' to be installed (missing or failed to import). Make sure to do 'pip install \"openllm[gptq]\"'")
    else:
      quantisation_config = create_gptq_config()
  elif quantise == 'awq':
    if not is_autoawq_available():
      raise MissingDependencyError("quantize='awq' requires 'auto-awq' to be installed (missing or failed to import). Make sure to do 'pip install \"openllm[awq]\"'.")
    else:
      quantisation_config = create_awq_config()
  else:
    raise ValueError(f"'quantize' must be one of ['int8', 'int4', 'gptq', 'awq'], got {quantise} instead.")
  return quantisation_config, attrs
