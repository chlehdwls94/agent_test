from google.adk.agents import Agent
from .prompt import (image_agent_instruction, architecture_agent_instruction, root_agent_instruction)
from .home_recommendation_tools import (
    ImageAnalyzer,
    ContextExtractor,
    ProductMatcher,
    RecommendationExplainer,
)
from .tools import generate_edit_image

# Agent for Home Recommendations
home_recommendation_agent = Agent(
    name="home_recommendation_agent",
    model="gemini-1.5-pro",
    description="An agent that recommends products based on a room image and user preferences",
    instructions=home_recommendation_agent_instruction,
    tools=[
        ImageAnalyzer,
        ContextExtractor,
        ProductMatcher,
        RecommendationExplainer,
    ],
)

# Agent for Image Generation
image_agent = Agent(
    name="image_agent",
    model="gemini-1.5-pro",
    description="An agent that generates and modifies images",
    instructions=image_agent_instruction,
    tools=[generate_edit_image],
)

# Agent for Architecture Analysis
architecture_agent = Agent(
    name="architecture_agent",
    model="gemini-1.5-pro",
    description="An agent that analyzes and explains software architecture diagrams",
    instructions=architecture_agent_instruction,
)

# Root Agent to orchestrate all other agents
root_agent = Agent(
    name="home_recommendation_root_agent",
    model="gemini-1.5-pro",
    description="A root agent that orchestrates other agents for home recommendations, image generation, and architecture analysis.",
    instructions=root_agent_instruction,
    sub_agents=[
        home_recommendation_agent,
        image_agent,
        architecture_agent,
    ],
)
