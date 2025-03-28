import json

from pydantic_ai import Agent
from pydantic_ai._result import ResultSchema


# class SubSchema(BaseModel):
#     mood: str = Field(
#         description="Your current outlook",
#     )
#     objective: str = Field(
#         description="Your current objective",
#     )
#
#
# class ExampleSchema(BaseModel):
#     thinking: str = Field(
#         description="Think things through before moving on. It helps to stay concise and strategic, and not repeat your previous thoughts much."
#     )
#     commands: List[str] = Field(
#         description="List of verbatim commands that will be input to the game. You should usually send only one, unless you have good reason, since you won't see the response until after all commands have been input."
#     )
#     details: SubSchema


class ArchitectFormatterAgent(Agent):
    def __init__(
        self, architect_model, formatter_model, response_type, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.architect_model = Agent(architect_model)
        self.formatter_model = Agent(formatter_model, result_type=response_type)

        schema_obj = ResultSchema.build(
            response_type=response_type,
            name="a",
            description="Example schema description",
        )
        schema = json.dumps(
            schema_obj.tools["a"].tool_def.parameters_json_schema, indent=2
        )
        self.architect_model.system_prompt(
            lambda: f"Please respond in the following schema:\n\n{schema}"
        )

    async def run(
        self,
        user_prompt: str,
        *,
        result_type=None,
        message_history=None,
        architect_model=None,
        formatter_model=None,
        deps=None,
        model_settings=None,
        usage_limits=None,
        usage=None,
        infer_name=True,
    ):
        architect_plan = await self.architect_model.run(
            user_prompt=user_prompt,
            result_type=None,
            message_history=message_history,
            model=architect_model,
            deps=deps,
            model_settings=model_settings,
            usage_limits=usage_limits,
            usage=usage,
            infer_name=infer_name,
        )  # todo check it has context obj
        formatter_prompt = f"{user_prompt}\n\n{architect_plan.data}\n\n---\n\nPlease correct any formatting issues in the response above, and ensure the response meets the requirements."

        formatted_response = await self.formatter_model.run(
            user_prompt=formatter_prompt,
            model=formatter_model,
            deps=deps,
            model_settings=model_settings,
            usage_limits=usage_limits,
            usage=usage,
            infer_name=infer_name,
        )
        return formatted_response


# test_agent = ArchitectFormatterAgent(
#     architect_model=OpenAIModel(
#         r1.replace("openrouter/", ""),
#         provider=OpenAIProvider(
#             base_url="https://openrouter.ai/api/v1",
#             api_key=OPENROUTER_API_KEY,
#         ),
#     ),
#     formatter_model=OpenAIModel(
#         gpt_4o_mini.replace("openrouter/", ""),
#         provider=OpenAIProvider(
#             base_url="https://openrouter.ai/api/v1",
#             api_key=OPENROUTER_API_KEY,
#         ),
#     ),
#     result_type=ExampleSchema,
# )


# async def main():
#     prompt = "You're playing zork. There's a white house in front of you."
#
#     result = await test_agent.run(prompt)
#     print(result)
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
