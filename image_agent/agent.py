from google.adk.agents import Agent
from .prompt import (image_agent_instruction, architecture_agent_instruction, root_agent_instruction)
from .home_recommendation_tools import (
    ImageAnalyzer,
    ContextExtractor,
    ProductMatcher,
    RecommendationExplainer,
)

home_recommendation_agent = Agent(
    name="home_recommendation_agent",
    model="gemini-2.5-pro",
    description="An agent that recommends products based on a room image and user preferences",
    tools=[
        ImageAnalyzer,
        ContextExtractor,
        ProductMatcher,
        RecommendationExplainer,
    ],
)

root_agent = Agent(
    name="home_recommendation_root_agent",
    model="gemini-2.5-pro",
    description="A root agent that orchestrates the home recommendation agent",
    sub_agents=[home_recommendation_agent],
)
