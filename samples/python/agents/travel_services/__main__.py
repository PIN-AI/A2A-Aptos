import logging
import os

import click
from common.aptos_config import AptosConfig

from agent import TravelAgent
from common.server import A2AServer
from common.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    MissingAPIKeyError,
)
from dotenv import load_dotenv
from task_manager import AgentTaskManager


load_dotenv()

# Configure logging to reduce verbosity  
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Reduce Google ADK and related library logs
logging.getLogger('google.adk.models.google_llm').setLevel(logging.ERROR)
logging.getLogger('google_genai.models').setLevel(logging.ERROR)
logging.getLogger('google_genai.types').setLevel(logging.ERROR)
logging.getLogger('httpx').setLevel(logging.ERROR)
logging.getLogger('uvicorn.access').setLevel(logging.ERROR)

# Keep important logs
logging.getLogger('__main__').setLevel(logging.INFO)
logging.getLogger('task_manager').setLevel(logging.INFO)
logging.getLogger('common.server.task_manager').setLevel(logging.INFO)


@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10004)
@click.option('--verify-signatures', is_flag=True, default=True, help='Enable signature verification')
@click.option('--aptos-address', default=None, help='Aptos address for Remote Agent (optional)')
def main(host, port, verify_signatures, aptos_address):
    try:
        # Check for API key only if Vertex AI is not configured
        if not os.getenv('GOOGLE_GENAI_USE_VERTEXAI') == 'TRUE':
            if not os.getenv('GOOGLE_API_KEY'):
                raise MissingAPIKeyError(
                    'GOOGLE_API_KEY environment variable not set and GOOGLE_GENAI_USE_VERTEXAI is not TRUE.'
                )

        # If aptos_address is not provided, try to get it from APTOS_PRIVATE_KEY environment variable
        if not aptos_address:
            aptos_private_key = os.environ.get('APTOS_PRIVATE_KEY')
            if aptos_private_key:
                try:
                    aptos_config = AptosConfig(private_key=aptos_private_key)
                    aptos_address = str(aptos_config.address)
                    logger.info(f"Generated aptos_address from APTOS_PRIVATE_KEY: {aptos_address}")
                except Exception as e:
                    logger.error(f"Error generating Aptos address from private key: {e}")
                    aptos_address = '0x123456789abcdef0123456789abcdef012345678'  # Default address
            else:
                logger.warning("APTOS_PRIVATE_KEY not set, using default aptos_address")
                aptos_address = '0x123456789abcdef0123456789abcdef012345678'  # Default address

        capabilities = AgentCapabilities(streaming=False)
        
        # Define agent skills
        planning_skill = AgentSkill(
            id='trip_planning',
            name='Trip Planning Tool',
            description='Helps users plan comprehensive travel itineraries with destinations, accommodations, and activities.',
            tags=['planning', 'itinerary', 'travel'],
            examples=[
                '帮我规划一个7天的日本关西之旅',
                '制定一个浪漫的巴黎5日游行程',
                '规划东南亚10天深度游'
            ],
        )
        
        hotel_skill = AgentSkill(
            id='hotel_services',
            name='Hotel Services Tool',
            description='Helps users search for hotels and make reservations worldwide.',
            tags=['hotel', 'booking', 'accommodation'],
            examples=[
                '东京有哪些好的酒店？',
                '我想预订巴黎香格里拉酒店',
                '泰国普吉岛的海滨度假村推荐'
            ],
        )
        
        flight_skill = AgentSkill(
            id='flight_services',
            name='Flight Services Tool', 
            description='Helps users search for flights and make airline reservations.',
            tags=['flight', 'booking', 'airline'],
            examples=[
                '从北京到东京的航班有哪些？',
                '我要预订明天的商务舱机票',
                '上海飞洛杉矶的直飞航班'
            ],
        )
        
        # Add aptos_address to AgentCard metadata
        agent_card = AgentCard(
            name='Travel Services Agent',
            description='This agent helps users plan trips, book hotels and flights, find destinations, and create comprehensive travel itineraries.',
            url=f'http://localhost:{port}/',
            version='1.0.0',
            defaultInputModes=TravelAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=TravelAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[planning_skill, hotel_skill, flight_skill],
            metadata={"aptos_address": aptos_address}  # Add aptos address
        )
        
        # Initialize the task manager with signature verification and save aptos_address
        logger.info(f"Initializing AgentTaskManager with signature verification: {verify_signatures}")
        agent = TravelAgent()
        task_manager = AgentTaskManager(
            agent=agent,
            verify_signatures=verify_signatures
        )
        # Set agent aptos address
        task_manager.agent_address = aptos_address
        logger.info(f"Agent aptos address set to: {aptos_address}")
        
        # Also set it as environment variable for easier access
        os.environ['AGENT_APTOS_ADDRESS'] = aptos_address
        
        server = A2AServer(
            agent_card=agent_card,
            task_manager=task_manager,
            host=host,
            port=port,
        )
        server.start()
    except MissingAPIKeyError as e:
        logger.error(f'Error: {e}')
        exit(1)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        exit(1)


if __name__ == '__main__':
    main() 