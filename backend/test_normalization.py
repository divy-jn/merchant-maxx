import os
import json
from litellm.exceptions import BadRequestError, RateLimitError
from langchain_litellm import ChatLiteLLM
from langchain_core.messages import HumanMessage, AIMessage

class NormalizedChatLiteLLM(ChatLiteLLM):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        try:
            return super()._generate(messages, stop, run_manager, **kwargs)
        except BadRequestError as e:
            msg = getattr(e, "message", "") or str(e)
            print(f">>> MSG IS: {msg!r}")
            if "Requests ending with a model turn" in msg or "INVALID_ARGUMENT" in msg:
                print(">>> Bubbling up genuine 400 Bad Request")
                raise e
            print(">>> Normalizing BadRequestError to RateLimitError")
            raise RateLimitError(
                message=msg,
                llm_provider=getattr(e, "llm_provider", "gemini"),
                model=getattr(e, "model", self.model)
            ) from e

def test_normalization():
    llm = NormalizedChatLiteLLM(
        model="gemini/gemini-3.6-flash",
        api_key=os.environ.get("LLM_API_KEY", "fake")
    )
    try:
        llm.invoke([HumanMessage("hi"), AIMessage("hello")])
    except Exception as e:
        print(f"Caught exception: {type(e)}")

if __name__ == "__main__":
    test_normalization()
