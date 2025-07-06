import logging
import os

import click
from common.aptos_config import AptosConfig

from agent import UberAgent
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
logging.basicConfig(level=logging.INFO)
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
logging.getLogger('agent').setLevel(logging.INFO)


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
        
        # Define agent skills for ride-hailing services
        driver_search_skill = AgentSkill(
            id='driver_search',
            name='Driver Search Tool',
            description='Helps users find nearby available drivers and check car availability in their area.',
            tags=['driver', 'search', 'availability', 'nearby'],
            examples=[
                '查找我附近的司机',
                '旧金山有哪些司机可用？',
                '2英里内有多少UberX司机？'
            ],
        )
        
        fare_estimation_skill = AgentSkill(
            id='fare_estimation',
            name='Fare Estimation Tool',
            description='Provides fare estimates for rides between different locations with various car types.',
            tags=['fare', 'estimate', 'pricing', 'cost'],
            examples=[
                '从SFO到市区要多少钱？',
                '估算一下从伯克利到帕罗奥图的车费',
                'UberBlack比UberX贵多少？'
            ],
        )
        
        ride_booking_skill = AgentSkill(
            id='ride_booking',
            name='Ride Booking Tool',
            description='Helps users book rides with driver assignment, payment confirmation, and blockchain verification.',
            tags=['booking', 'ride', 'payment', 'confirmation'],
            examples=[
                '我要叫一辆车去机场',
                '预订一辆UberXL去斯坦福大学',
                '现在叫车从downtown去Oakland'
            ],
        )
        
        route_planning_skill = AgentSkill(
            id='route_planning',
            name='Route Planning Tool',
            description='Provides route information, traffic conditions, and travel time estimates.',
            tags=['route', 'traffic', 'navigation', 'time'],
            examples=[
                '从旧金山到圣何塞最快的路线是什么？',
                '现在去机场会堵车吗？',
                '有什么备选路线推荐？'
            ],
        )
        
        # Add aptos_address to AgentCard metadata
        agent_card = AgentCard(
            name='Uber Services Agent',
            description='This agent helps users with ride-hailing services including finding drivers, estimating fares, booking rides, and route planning in the Bay Area.',
            url=f'http://localhost:{port}/',
            version='1.0.0',
            defaultInputModes=UberAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=UberAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[driver_search_skill, fare_estimation_skill, ride_booking_skill, route_planning_skill],
            metadata={"aptos_address": aptos_address}  # Add aptos address
        )
        
        # Initialize the task manager with signature verification and save aptos_address
        logger.info(f"Initializing AgentTaskManager with signature verification: {verify_signatures}")
        agent = UberAgent()
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
