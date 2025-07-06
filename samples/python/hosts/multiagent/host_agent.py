import base64
import json
import logging
import os
import uuid
from datetime import datetime

from common.client import A2ACardResolver
from common.types import (
    AgentCard,
    DataPart,
    Message,
    Part,
    Task,
    TaskSendParams,
    TaskState,
    TextPart,
)
from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.tool_context import ToolContext
from google.genai import types
# Import Aptos related libraries
from common.aptos_config import AptosConfig
from common.aptos_blockchain import AptosTaskManager, AptosSignatureManager

from .remote_agent_connection import RemoteAgentConnections, TaskUpdateCallback


logger = logging.getLogger(__name__)


class HostAgent:
    """The host agent.

    This is the agent responsible for choosing which remote agents to send
    tasks to and coordinate their work.
    """

    def __init__(
        self,
        remote_agent_addresses: list[str],
        task_callback: TaskUpdateCallback | None = None,
        private_key: str = None,  # Add private key parameter
    ):
        self.task_callback = task_callback
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        
        # Initialize Aptos configuration
        self.aptos_config = AptosConfig(private_key)
        self.aptos_task_manager = AptosTaskManager(self.aptos_config)
        self.aptos_signature_manager = AptosSignatureManager(self.aptos_config.account) if self.aptos_config.account else None
        
        # Set Aptos address for backward compatibility
        self.aptos_address = str(self.aptos_config.address) if self.aptos_config.address else None
                
        for address in remote_agent_addresses:
            card_resolver = A2ACardResolver(address)
            card = card_resolver.get_agent_card()
            remote_connection = RemoteAgentConnections(card)
            self.remote_agent_connections[card.name] = remote_connection
            self.cards[card.name] = card
        agent_info = []
        for ra in self.list_remote_agents():
            agent_info.append(json.dumps(ra))
        self.agents = '\n'.join(agent_info)

    def register_agent_card(self, card: AgentCard):
        remote_connection = RemoteAgentConnections(card)
        self.remote_agent_connections[card.name] = remote_connection
        self.cards[card.name] = card
        agent_info = []
        for ra in self.list_remote_agents():
            agent_info.append(json.dumps(ra))
        self.agents = '\n'.join(agent_info)

    def create_agent(self) -> Agent:
        return Agent(
            model='gemini-2.0-flash-001',
            name='host_agent',
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                'This agent orchestrates the decomposition of the user request into'
                ' tasks that can be performed by the child agents.'
            ),
            tools=[
                self.list_remote_agents,
                self.send_task,
                self.confirm_task,
                self.get_user_context,
            ],
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        current_agent = self.check_state(context)
        return f"""You are an expert delegator that can delegate the user request to the
appropriate remote agents.

Discovery:
- You can use `list_remote_agents` to list the available remote agents you
can use to delegate the task.
- You can use `get_user_context` to understand the user's current situation, preferences,
and location, which will help you make better decisions.

Execution:
- For IMPORTANT TASKS that involve real-world actions, transactions, or commitments, 
  use `confirm_task` to provide blockchain-level verification and security. This includes:
  * Food ordering and delivery requests
  * Restaurant reservations
  * Payment processing
  * Booking confirmations
  * Any task that involves spending money or making commitments
  
- For INFORMATIONAL QUERIES and simple interactions, use `send_task`:
  * Searching for restaurants or information
  * Getting recommendations
  * Asking questions
  * General conversation

- PRIORITIZE `confirm_task` for actionable requests. When a user makes a clear request
  like "order food", "book a table", or "make a reservation", use `confirm_task` 
  to ensure the task is properly verified on the blockchain.

- Be sure to include the remote agent name when you respond to the user.

- When the request is related to food or dining, first check the user context with
`get_user_context` to understand their preferences and current situation.

You can use `check_pending_task_states` to check the states of the pending
tasks.

When you receive requests like "I want to order food", use the user context to be more proactive
and helpful. Don't ask for information that is already available in the user context.
For example, instead of asking which restaurant, suggest their favorite restaurant
from the context.

IMPORTANT: When delegating food orders to the Food Ordering Agent, always include the user's 
delivery address from the user context in your message. For example: "Please order Van Damme 
pizza from Za Pizza for delivery to 2240 Calle De Luna, Santa Clara" instead of just 
"I want to order Van Damme pizza from Za Pizza".

Please rely on tools to address the request, and don't make up the response. If you are not sure, please ask the user for more details.
Focus on the most recent parts of the conversation primarily.

If there is an active agent, send the request to that agent with the update task tool.

Agents:
{self.agents}

Current agent: {current_agent['active_agent']}
"""

    def check_state(self, context: ReadonlyContext):
        state = context.state
        if (
            'session_id' in state
            and 'session_active' in state
            and state['session_active']
            and 'agent' in state
        ):
            return {'active_agent': f'{state["agent"]}'}
        return {'active_agent': 'None'}

    def before_model_callback(
        self, callback_context: CallbackContext, llm_request
    ):
        state = callback_context.state
        if 'session_active' not in state or not state['session_active']:
            if 'session_id' not in state:
                state['session_id'] = str(uuid.uuid4())
            state['session_active'] = True

    def list_remote_agents(self):
        """List the available remote agents you can use to delegate the task."""
        if not self.remote_agent_connections:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            remote_agent_info.append(
                {'name': card.name, 'description': card.description}
            )
        return remote_agent_info

    def get_user_context(self):
        """Get the current user context information to help understand user needs better."""
        # Hardcoded user information for demo purposes
        user_context = {
            "environment": {
                "weather": "currently bad weather, not suitable for going out",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "preferences": {
                "food_preference": "pizza",
                "favorite_restaurant": "Za Pizza",
                "favorite_dish": "Van Damme pizza"
            },
            "location": {
                "current_location": "home",
                "address": "2240 Calle De Luna, Santa Clara"
            }
        }
        
        return user_context

    def sign_message(self, message: str) -> str:
        """Sign a message using the host agent's Aptos private key.
        
        Args:
            message: The message to sign.
            
        Returns:
            The hex string of the signature if successful, or None if failed.
        """
        if not self.aptos_signature_manager:
            return None
            
        try:
            signature = self.aptos_signature_manager.sign_message(message)
            if signature:
                logger.debug(f"[APTOS NETWORK] Host Agent: signed message with Ed25519, address: {self.aptos_address}")
            return signature
        except Exception as e:
            logger.error(f"Error signing message with Ed25519: {e}")
            return None

    async def confirm_task(
        self, agent_name: str, message: str, tool_context: ToolContext
    ):
        """Interacts with Aptos blockchain to confirm tasks and sends them to remote agents.
        
        This method is similar to send_task but registers task confirmation on Aptos blockchain.
        
        Args:
          agent_name: The name of the remote agent
          message: The task message to send to the agent
          tool_context: The tool context this method runs in
        
        Returns:
          A dictionary of JSON data including blockchain confirmation
        """
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f'Agent {agent_name} not found')
            
        # Set state and get necessary information
        state = tool_context.state
        state['agent'] = agent_name
        card = self.cards[agent_name]
        client = self.remote_agent_connections[agent_name]
        if not client:
            raise ValueError(f'Client not available for {agent_name}')
            
        # Get or create task ID and session ID
        if 'task_id' in state:
            taskId = state['task_id']
        else:
            taskId = str(uuid.uuid4())
        sessionId = state['session_id']
        
        # Get remote agent's Aptos address
        remote_agent_address = None
        if hasattr(card, 'metadata') and card.metadata:
            remote_agent_address = card.metadata.get('aptos_address') or card.metadata.get('ethereum_address')
            
        # If not found in card metadata, try environment variables
        if not remote_agent_address:
            remote_agent_address = os.environ.get('REMOTE_AGENT_APTOS_ADDRESS', "0x69029bc61f9828ed712a9238f70b4fe629b35144cd638a50f60bd278916b33c5")
            
        if not remote_agent_address:
            raise ValueError(f"Could not determine Aptos address for remote agent {agent_name}")
            
        # Check Aptos connection
        try:
            if not await self.aptos_config.is_connected():
                raise ConnectionError("Unable to connect to Aptos network")
        except Exception as e:
            logger.warning(f"Aptos connection error: {e}")
            logger.info(f"Falling back to regular send_task without blockchain confirmation")
            # Fallback to regular send_task when blockchain is not available
            return await self.send_task(agent_name, message, tool_context)
            
        # Cannot proceed without account
        if not self.aptos_config.account:
            raise ValueError("Host Agent has no Aptos account configured, cannot perform blockchain confirmation")
            
        # Default bounty: 0.01 APT (in octas)
        bounty = int(os.environ.get('APTOS_TASK_BOUNTY', "1000000"))  # 0.01 APT = 1,000,000 octas
        deadline_seconds = int(os.environ.get('APTOS_TASK_DEADLINE', "7200"))  # 2 hours default
        
        try:
            # Create task on Aptos blockchain using sessionId as task_id
            task_description = f"A2A Task: {message[:100]}..."  # Truncate for description
            
            # Add detailed logging for debugging
            print(f"[APTOS DEBUG] Creating task with parameters:")
            print(f"  task_id: {sessionId}")
            print(f"  service_agent: {remote_agent_address}")
            print(f"  amount_apt: {bounty}")
            print(f"  deadline_seconds: {deadline_seconds}")
            print(f"  description: {task_description}")
            print(f"  host_address: {self.aptos_config.address}")
            print(f"  module_address: {self.aptos_config.module_address}")

            result = await self.aptos_task_manager.create_task(
                task_id=sessionId,  # Use sessionId as task_id for consistency
                service_agent=remote_agent_address,
                amount_apt=bounty,
                deadline_seconds=deadline_seconds,
                description=task_description
            )
            
            if not result.get('success'):
                raise Exception(f"Failed to create task on Aptos: {result.get('error')}")
                
            tx_hash = result.get('tx_hash')
            logger.info(f"[APTOS NETWORK] Host Agent: task created successfully! tx: {tx_hash}")
            
        except Exception as e:
            logger.warning(f"Aptos transaction error: {e}")
            logger.info(f"Falling back to regular send_task without blockchain confirmation")
            # Fallback to regular send_task when blockchain transaction fails
            return await self.send_task(agent_name, message, tool_context)
        
        # Prepare message metadata
        messageId = ''
        metadata = {}
        if 'input_message_metadata' in state:
            metadata.update(**state['input_message_metadata'])
            if 'message_id' in state['input_message_metadata']:
                messageId = state['input_message_metadata']['message_id']
        if not messageId:
            messageId = str(uuid.uuid4())
            
        # Add basic metadata
        metadata.update(conversation_id=sessionId, message_id=messageId)
        
        # Add signature information to metadata
        signature = None
        if self.aptos_address:
            message_to_sign = f"{self.aptos_address}{sessionId}"
            signature = self.sign_message(message_to_sign)
            if signature:
                metadata["auth"] = {
                    "address": self.aptos_address,
                    "signature": signature
                }
        
        # Add blockchain confirmation information to metadata
        metadata["blockchain"] = {
            "createTask": {
                "tx_hash": tx_hash,
                "module_address": self.aptos_config.module_address
            }
        }
        
        # Create task request
        request: TaskSendParams = TaskSendParams(
            id=taskId,
            sessionId=sessionId,
            message=Message(
                role='user',
                parts=[TextPart(text=message)],
                metadata=metadata,
            ),
            acceptedOutputModes=['text', 'text/plain', 'image/png'],
            metadata={'conversation_id': sessionId},
        )
        
        # Send task
        task = await client.send_task(request, self.task_callback)
        
        # Check if task is None
        if not task:
            logger.error(f"Received None task from agent {agent_name}")
            raise ValueError(f"Agent {agent_name} returned no task result")
            
        # Check if task.status is None
        if not task.status:
            logger.error(f"Task {task.id} has no status")
            raise ValueError(f"Agent {agent_name} task has no status")
        
        # Update session state
        state['session_active'] = task.status.state not in [
            TaskState.COMPLETED,
            TaskState.CANCELED,
            TaskState.FAILED,
            TaskState.UNKNOWN,
        ]
        
        # Handle task status
        if task.status.state == TaskState.INPUT_REQUIRED:
            tool_context.actions.skip_summarization = True
            tool_context.actions.escalate = True
        elif task.status.state == TaskState.CANCELED:
            raise ValueError(f'Agent {agent_name} task {task.id} is cancelled')
        elif task.status.state == TaskState.FAILED:
            raise ValueError(f'Agent {agent_name} task {task.id} failed')
            
        # Process response
        response = []
        if task.status and task.status.message:
            response.extend(
                convert_parts(task.status.message.parts, tool_context)
            )
        if task.artifacts:
            for artifact in task.artifacts:
                if artifact and artifact.parts:
                    response.extend(convert_parts(artifact.parts, tool_context))
                
        # Return result with blockchain confirmation information
        response.append({
            "blockchain_confirmation": {
                "createTask": {
                    "transaction_hash": tx_hash,
                    "module_address": self.aptos_config.module_address,
                    "task_id": sessionId,
                    "gas_used": result.get('gas_used', 0)
                }
            }
        })
        
        return response

    async def send_task(
        self, agent_name: str, message: str, tool_context: ToolContext
    ):
        """Sends a task either streaming (if supported) or non-streaming.

        This will send a message to the remote agent named agent_name.

        Args:
          agent_name: The name of the agent to send the task to.
          message: The message to send to the agent for the task.
          tool_context: The tool context this method runs in.

        Yields:
          A dictionary of JSON data.
        """
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f'Agent {agent_name} not found')
        state = tool_context.state
        state['agent'] = agent_name
        card = self.cards[agent_name]
        client = self.remote_agent_connections[agent_name]
        if not client:
            raise ValueError(f'Client not available for {agent_name}')
        if 'task_id' in state:
            taskId = state['task_id']
        else:
            taskId = str(uuid.uuid4())
        sessionId = state['session_id']
        
        # Generate Ed25519 signature for authentication
        signature = None
        if self.aptos_signature_manager and self.aptos_address:
            # Sign message combining agent address and session ID
            message_to_sign = f"{self.aptos_address}{sessionId}"
            signature = self.sign_message(message_to_sign)
        
        task: Task
        messageId = ''
        metadata = {}
        if 'input_message_metadata' in state:
            metadata.update(**state['input_message_metadata'])
            if 'message_id' in state['input_message_metadata']:
                messageId = state['input_message_metadata']['message_id']
        if not messageId:
            messageId = str(uuid.uuid4())
            
        # Add basic metadata
        metadata.update(conversation_id=sessionId, message_id=messageId)
        
        # Add signature information to metadata if available
        if signature and self.aptos_address:
            metadata.update({
                "auth": {
                    "address": self.aptos_address,
                    "signature": signature
                }
            })
        
        request: TaskSendParams = TaskSendParams(
            id=taskId,
            sessionId=sessionId,
            message=Message(
                role='user',
                parts=[TextPart(text=message)],
                metadata=metadata,
            ),
            acceptedOutputModes=['text', 'text/plain', 'image/png'],
            # pushNotification=None,
            metadata={'conversation_id': sessionId},
        )
        task = await client.send_task(request, self.task_callback)
        
        # Check if task is None
        if not task:
            logger.error(f"Received None task from agent {agent_name}")
            raise ValueError(f"Agent {agent_name} returned no task result")
            
        # Check if task.status is None
        if not task.status:
            logger.error(f"Task {task.id} has no status")
            raise ValueError(f"Agent {agent_name} task has no status")
        
        # Assume completion unless a state returns that isn't complete
        state['session_active'] = task.status.state not in [
            TaskState.COMPLETED,
            TaskState.CANCELED,
            TaskState.FAILED,
            TaskState.UNKNOWN,
        ]
        if task.status.state == TaskState.INPUT_REQUIRED:
            # Force user input back
            tool_context.actions.skip_summarization = True
            tool_context.actions.escalate = True
        elif task.status.state == TaskState.CANCELED:
            # Open question, should we return some info for cancellation instead
            raise ValueError(f'Agent {agent_name} task {task.id} is cancelled')
        elif task.status.state == TaskState.FAILED:
            # Raise error for failure
            raise ValueError(f'Agent {agent_name} task {task.id} failed')
        response = []
        if task.status and task.status.message:
            # Assume the information is in the task message.
            response.extend(
                convert_parts(task.status.message.parts, tool_context)
            )
        if task.artifacts:
            for artifact in task.artifacts:
                if artifact and artifact.parts:
                    response.extend(convert_parts(artifact.parts, tool_context))
        return response


def convert_parts(parts: list[Part], tool_context: ToolContext):
    rval = []
    for p in parts:
        rval.append(convert_part(p, tool_context))
    return rval


def convert_part(part: Part, tool_context: ToolContext):
    if part.type == 'text':
        return part.text
    if part.type == 'data':
        return part.data
    if part.type == 'file':
        # Repackage A2A FilePart to google.genai Blob
        # Currently not considering plain text as files
        file_id = part.file.name
        file_bytes = base64.b64decode(part.file.bytes)
        file_part = types.Part(
            inline_data=types.Blob(
                mime_type=part.file.mimeType, data=file_bytes
            )
        )
        tool_context.save_artifact(file_id, file_part)
        tool_context.actions.skip_summarization = True
        tool_context.actions.escalate = True
        return DataPart(data={'artifact-file-id': file_id})
    return f'Unknown type: {part.type}'
