"""
Author: Karan Bansal (@karanb192)
License: MIT License
"""

from pydantic import BaseModel, Field
import httpx
from typing import Dict, List, Optional, Any
import logging
import hashlib


class Pipe:
    class Valves(BaseModel):
        NAME_PREFIX: str = Field(
            default="OpenAI: ",
            description="Prefix to be added before model names.",
        )
        BASE_URL: str = Field(
            default="https://api.openai.com/v1",
            description="Base URL for OpenAI API.",
        )
        API_KEYS: str = Field(
            default="",
            description="API keys for OpenAI, use comma to separate multiple keys",
        )
        THINKING_EFFORT: str = Field(
            default="medium",
            description="Reasoning effort: low, medium, high",
        )
        SHOW_TOKEN_STATS: bool = Field(
            default=True,
            description="Display token usage statistics with each response",
        )
        SHOW_CUMULATIVE_COST: bool = Field(
            default=True,
            description="Show cumulative cost for the entire conversation",
        )
        MAX_OUTPUT_TOKENS: int = Field(
            default=3200,
            description="Maximum number of output tokens (1-32768)",
        )
        TIMEOUT_SECONDS: int = Field(
            default=600,
            description="Request timeout in seconds",
        )
        DEBUG_MODE: bool = Field(
            default=False,
            description="Enable debug logging to see raw API responses",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.openai_response_models = ["o1-pro", "o3-pro"]
        self.api_key_index = 0
        self.logger = self._setup_logger()
        # Store conversation costs per user/conversation
        self.conversation_costs = {}

    def _setup_logger(self):
        """Setup logging for debugging"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        return logger

    def _get_conversation_id(self, body: dict, user: dict) -> str:
        """Generate a unique conversation identifier based on the FIRST user message only"""
        # Get the first user message to create a stable conversation ID
        first_user_message = None

        for msg in body.get("messages", []):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Handle multi-modal content
                    text_content = " ".join(
                        [
                            item.get("text", "")
                            for item in content
                            if item.get("type") == "text"
                        ]
                    )
                    first_user_message = text_content
                else:
                    first_user_message = str(content)
                break  # Only use the FIRST user message

        if not first_user_message:
            first_user_message = "no_message"

        # Create a hash based on user ID and first message only
        user_id = user.get("id", "unknown")

        # Use first 50 chars of first message for uniqueness
        message_key = first_user_message[:50]

        # Create stable conversation ID
        conv_hash = hashlib.sha256(f"{user_id}_{message_key}".encode()).hexdigest()[:16]
        conv_id = f"conv_{user_id}_{conv_hash}"

        if self.valves.DEBUG_MODE:
            user_msg_count = len(
                [m for m in body.get("messages", []) if m.get("role") == "user"]
            )
            self.logger.info(
                f"Conversation ID: {conv_id}, User messages in history: {user_msg_count}"
            )
            self.logger.info(f"First message preview: {message_key[:30]}...")

        return conv_id

    def _update_conversation_cost(self, conv_id: str, cost: float, tokens: Dict):
        """Update cumulative cost for a conversation"""
        if conv_id not in self.conversation_costs:
            self.conversation_costs[conv_id] = {
                "total_cost": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_reasoning_tokens": 0,
                "message_count": 0,
            }

        # Add to existing totals (not replace)
        self.conversation_costs[conv_id]["total_cost"] += cost
        self.conversation_costs[conv_id]["total_input_tokens"] += tokens.get("input", 0)
        self.conversation_costs[conv_id]["total_output_tokens"] += tokens.get(
            "output", 0
        )
        self.conversation_costs[conv_id]["total_reasoning_tokens"] += tokens.get(
            "reasoning", 0
        )
        self.conversation_costs[conv_id]["message_count"] += 1

        if self.valves.DEBUG_MODE:
            self.logger.info(
                f"Updated conversation {conv_id}: Total cost now ${self.conversation_costs[conv_id]['total_cost']:.4f}"
            )

    def _get_next_api_key(self) -> str:
        """Round-robin API key selection"""
        keys = [k.strip() for k in self.valves.API_KEYS.split(",") if k.strip()]
        if not keys:
            raise ValueError("No API keys configured")

        key = keys[self.api_key_index % len(keys)]
        self.api_key_index += 1
        return key

    def pipes(self):
        """Return available models"""
        res = []
        for model in self.openai_response_models:
            res.append({"name": f"{self.valves.NAME_PREFIX}{model}", "id": model})
        return res

    def _transform_messages(self, messages: List[Dict]) -> List[Dict]:
        """Transform Open Web UI messages to Responses API format"""
        new_messages = []

        for message in messages:
            try:
                role = message.get("role")
                content = message.get("content")

                if role == "user":
                    if isinstance(content, list):
                        transformed_content = []
                        for item in content:
                            if item["type"] == "text":
                                transformed_content.append(
                                    {"type": "input_text", "text": item["text"]}
                                )
                            elif item["type"] == "image_url":
                                transformed_content.append(
                                    {
                                        "type": "input_image",
                                        "image_url": item["image_url"]["url"],
                                    }
                                )
                        new_messages.append(
                            {"role": "user", "content": transformed_content}
                        )
                    else:
                        new_messages.append(
                            {
                                "role": "user",
                                "content": [{"type": "input_text", "text": content}],
                            }
                        )

                elif role == "assistant":
                    new_messages.append(
                        {
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": content}],
                        }
                    )

                elif role == "system":
                    new_messages.append(
                        {
                            "role": "system",
                            "content": [{"type": "input_text", "text": content}],
                        }
                    )

            except Exception as e:
                self.logger.error(f"Message transformation error: {e}")
                raise ValueError(f"Invalid message format: {message}")

        return new_messages

    def _extract_text_from_output(self, output_items: List[Any]) -> str:
        """Extract text from output array"""
        text_parts = []

        for item in output_items:
            if isinstance(item, dict):
                # Check if it's a message type
                if item.get("type") == "message" and item.get("role") == "assistant":
                    content_items = item.get("content", [])
                    for content in content_items:
                        if (
                            isinstance(content, dict)
                            and content.get("type") == "output_text"
                        ):
                            text = content.get("text", "")
                            if text:
                                text_parts.append(text)
                # Check for direct text content
                elif "text" in item:
                    text_parts.append(item["text"])
                elif "content" in item:
                    if isinstance(item["content"], str):
                        text_parts.append(item["content"])
                    elif isinstance(item["content"], list):
                        for content in item["content"]:
                            if isinstance(content, dict) and "text" in content:
                                text_parts.append(content["text"])
            elif isinstance(item, str):
                text_parts.append(item)

        return "\n".join(text_parts)

    def _format_token_stats(
        self,
        usage: Dict,
        model_id: str,
        status: str = "completed",
        incomplete_reason: str = None,
        conv_id: str = None,
        current_cost: float = 0.0,
    ) -> str:
        """Format token usage statistics for display"""
        if not usage or not self.valves.SHOW_TOKEN_STATS:
            return ""

        stats = f"\n\n---\n📊 **Token Usage (This Message)**:\n"

        # Extract token counts
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        # Check for reasoning tokens in output_tokens_details
        reasoning_tokens = 0
        if "output_tokens_details" in usage:
            reasoning_tokens = usage["output_tokens_details"].get("reasoning_tokens", 0)

        stats += f"- Input: {input_tokens:,} tokens\n"

        if reasoning_tokens > 0:
            stats += f"- Reasoning: {reasoning_tokens:,} tokens\n"

        stats += f"- Output: {output_tokens:,} tokens\n"
        stats += f"- Total: {total_tokens:,} tokens\n"
        stats += f"- **Cost for this message**: ${current_cost:.4f}\n"

        # Add cumulative stats if enabled
        if (
            self.valves.SHOW_CUMULATIVE_COST
            and conv_id
            and conv_id in self.conversation_costs
        ):
            conv_stats = self.conversation_costs[conv_id]
            stats += f"\n💰 **Conversation Totals**:\n"
            stats += f"- Messages: {conv_stats['message_count']}\n"
            stats += f"- Total Input: {conv_stats['total_input_tokens']:,} tokens\n"
            if conv_stats["total_reasoning_tokens"] > 0:
                stats += f"- Total Reasoning: {conv_stats['total_reasoning_tokens']:,} tokens\n"
            stats += f"- Total Output: {conv_stats['total_output_tokens']:,} tokens\n"
            stats += f"- **Total Cost**: ${conv_stats['total_cost']:.4f}\n"

        # Add status information
        if status == "incomplete":
            stats += f"\n⚠️ **Response Status**: Incomplete"
            if incomplete_reason:
                stats += f" (Reason: {incomplete_reason})"
            stats += "\n"

        stats += "---"
        return stats

    async def pipe(self, body: dict, __user__: dict):
        """Main pipeline function"""
        try:
            # Get conversation ID (stable across messages)
            conv_id = self._get_conversation_id(body, __user__)

            # Get API key
            api_key = self._get_next_api_key()

            # Setup headers
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            # Extract model ID
            model_id = body["model"][body["model"].find(".") + 1 :]

            if model_id not in self.openai_response_models:
                yield f"Error: Model {model_id} not supported. Only o1-pro and o3-pro are available."
                return

            # Build payload (non-streaming for accurate token counts)
            payload = {
                "model": model_id,
                "reasoning": {"effort": self.valves.THINKING_EFFORT.strip()},
                "max_output_tokens": min(max(self.valves.MAX_OUTPUT_TOKENS, 1), 32768),
            }

            # Transform messages
            payload["input"] = self._transform_messages(body["messages"])

            # Get the actual message count from conversation tracking
            current_message_number = 1
            if conv_id in self.conversation_costs:
                current_message_number = (
                    self.conversation_costs[conv_id]["message_count"] + 1
                )

            # Show processing message
            yield f"🔄 Processing with {model_id} (Message #{current_message_number} in conversation)...\n\n"

            async with httpx.AsyncClient(timeout=self.valves.TIMEOUT_SECONDS) as client:
                # Make non-streaming request
                response = await client.post(
                    f"{self.valves.BASE_URL}/responses",
                    json=payload,
                    headers=headers,
                )

                if response.status_code != 200:
                    error_text = response.text
                    yield f"Error: {response.status_code} {error_text}"
                    return

                # Parse the complete response
                response_data = response.json()

                # Debug log if enabled
                if self.valves.DEBUG_MODE:
                    self.logger.info(f"Response keys: {list(response_data.keys())}")

                # Extract the output text - try multiple methods
                output_text = None

                # Method 1: Direct output_text field
                if "output_text" in response_data and response_data["output_text"]:
                    output_text = response_data["output_text"]

                # Method 2: Parse from output array
                if not output_text and "output" in response_data:
                    output_text = self._extract_text_from_output(
                        response_data["output"]
                    )

                # Method 3: Check in other possible locations
                if not output_text:
                    # Try extracting from string representation of output
                    output_str = str(response_data.get("output", ""))
                    if "text='" in output_str or 'text="' in output_str:
                        # Extract text between quotes
                        import re

                        matches = re.findall(r"text=['\"]([^'\"]+)['\"]", output_str)
                        if matches:
                            output_text = "\n".join(matches)

                if output_text:
                    yield output_text
                else:
                    yield "No response text found in the API response."

                # Check response status
                status = response_data.get("status", "completed")
                incomplete_reason = None
                if status == "incomplete":
                    incomplete_details = response_data.get("incomplete_details", {})
                    incomplete_reason = incomplete_details.get("reason", "Unknown")

                    yield f"\n\n⚠️ **Note**: Response was truncated due to: {incomplete_reason}"
                    if incomplete_reason == "max_output_tokens":
                        yield f"\nConsider increasing MAX_OUTPUT_TOKENS (currently set to {self.valves.MAX_OUTPUT_TOKENS})"

                # Extract and display tools used
                tools_used = []
                output_items = response_data.get("output", [])
                for item in output_items:
                    if isinstance(item, dict) and item.get("type") in [
                        "file_search",
                        "function",
                    ]:
                        tools_used.append(item["type"])

                if tools_used:
                    yield f"\n\n🔧 **Tools used**: {', '.join(set(tools_used))}"

                # Calculate costs and update conversation totals
                usage_data = response_data.get("usage", {})
                if usage_data:
                    # Calculate current message cost
                    pricing = {
                        "o3-pro": {"input": 20, "output": 80},
                        "o1-pro": {"input": 150, "output": 600},
                    }

                    current_cost = 0.0
                    if model_id in pricing:
                        input_tokens = usage_data.get("input_tokens", 0)
                        output_tokens = usage_data.get("output_tokens", 0)
                        reasoning_tokens = 0
                        if "output_tokens_details" in usage_data:
                            reasoning_tokens = usage_data["output_tokens_details"].get(
                                "reasoning_tokens", 0
                            )

                        input_cost = (input_tokens / 1_000_000) * pricing[model_id][
                            "input"
                        ]
                        output_cost = (output_tokens / 1_000_000) * pricing[model_id][
                            "output"
                        ]
                        reasoning_cost = 0
                        if reasoning_tokens > 0 and model_id == "o3-pro":
                            reasoning_cost = (reasoning_tokens / 1_000_000) * pricing[
                                model_id
                            ]["output"]

                        current_cost = input_cost + output_cost + reasoning_cost

                        # Update conversation totals BEFORE displaying stats
                        self._update_conversation_cost(
                            conv_id,
                            current_cost,
                            {
                                "input": input_tokens,
                                "output": output_tokens,
                                "reasoning": reasoning_tokens,
                            },
                        )

                    # Display token statistics (will show updated totals)
                    stats = self._format_token_stats(
                        usage_data,
                        model_id,
                        status,
                        incomplete_reason,
                        conv_id,
                        current_cost,
                    )
                    if stats:
                        yield stats
                else:
                    if self.valves.SHOW_TOKEN_STATS:
                        yield "\n\n---\n📊 **Token Usage**: Not available in response\n---"

        except httpx.TimeoutException:
            yield f"Error: Request timed out after {self.valves.TIMEOUT_SECONDS} seconds."
        except Exception as e:
            self.logger.error(f"Pipeline error: {e}", exc_info=True)
            yield f"Error: {str(e)}"
            return
