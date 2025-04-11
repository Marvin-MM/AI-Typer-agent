import os
import logging
from pathlib import Path
import tempfile
import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, SecretStr
import streamlit as st
from browser_use import Agent, Browser
from browser_use import BrowserConfig
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from right_hand import DocumentRetyper

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

class LoginCredentials(BaseModel):
    reg_number: str = Field(..., description="VClass registration number")
    password: str = Field(..., description="VClass password")

class TypingTask(BaseModel):
    content: str = Field(..., description="Content to be typed")
    preserve_formatting: bool = Field(True, description="Whether to preserve formatting")

class VClassAutomation:
    """Class to handle VClass automation using browser-use"""
    
    def __init__(self, headless: bool = True, typing_speed: int = 25):
        """Initialize the VClass automation
        
        Args:
            headless: Whether to run browser in headless mode
            typing_speed: Characters per second for typing (25 is more accurate than 40)
        """
        self.headless = headless
        self.typing_speed = typing_speed
        self.screenshots = []
        self.max_retries = 2  # Add retries for reliability

    @asynccontextmanager
    async def get_browser(self):
        """Context manager for browser instance that ensures proper cleanup"""
        browser = None
        try:
            # Create browser with proper configuration
            browser_config = BrowserConfig(
                headless=self.headless,
                chrome_instance_path='/usr/bin/google-chrome',
                # Add timeout for better reliability
                # timeout=60000  # 60 seconds in ms
            )
            
            browser = Browser(config=browser_config)
            logger.info("Browser instance created")
            yield browser
        finally:
            # Always clean up browser resources
            if browser:
                try:
                    await browser.close()
                    logger.info("Browser instance closed properly")
                except Exception as e:
                    logger.error(f"Error closing browser: {str(e)}")

    async def run_automation(self, 
                      reg_number: str, 
                      password: str, 
                      document_content: str,
                      take_screenshots: bool = True,
                      progress_callback = None) -> Dict[str, Any]:
        """Run the VClass automation process with improved accuracy and completion
        
        Args:
            reg_number: VClass registration number
            password: VClass password
            document_content: Document content to type
            take_screenshots: Whether to capture screenshots
            progress_callback: Callback function for progress updates
            
        Returns:
            Dictionary with results
        """
        attempts = 0
        
        while attempts <= self.max_retries:
            try:
                # Update progress
                if progress_callback:
                    progress_message = "Initializing browser automation..." if attempts == 0 else f"Retry attempt {attempts}..."
                    progress_callback(progress_message, 0.2)
                
                # Improved task description with specific accuracy and completion instructions
                task_description = f"""
                TASK: Open VClass and Navigate to online editor and Tap to the Start of the Cursor Blinking and Stop Their:
                STEPS:
                1. Go to https://vclass.ac/login
                2. Log in with: 
                   - Registration number: {reg_number}
                   - Password: {password}
                3. Navigate to coursework section and find the online editor
                4. Click on the editor to focus it
                5. Ensure the cursor is in the correct position and stop then leaving cursor blink.
                """
                
                # Use the browser context manager
                async with self.get_browser() as browser:
                    # Configure the LLM with Gemini - improved settings
                    llm = ChatGoogleGenerativeAI(
                        
                        model='gemini-2.0-flash-exp',
                        api_key=SecretStr(api_key),
                        temperature=0.1,  # Lower temperature for even more deterministic behavior
                        max_output_tokens=4096,  # Increased token limit
                        top_p=0.95,  # Added for more focused output
                        top_k=40  # Added for more focused output
                    )
                    
                    # planner_llm = ChatOpenAI(base_url='https://api.deepseek.com/v1', model='deepseek-chat', api_key=SecretStr(api_key)))

                    agent = Agent(
                        task=task_description,
                        llm=llm,
                        browser=browser,
                        # use_vision=True,
                        # planner_llm=planner_llm,
                        # use_vision_for_planner=False,
                        # planner_interval=4,
                        
                                            
                    )


                    
                    # Update progress
                    if progress_callback:
                        progress_callback("Openining Chrome", 0.3)
                    
                    # Run the agent
                    result = await agent.run()
                    
                    # Take multiple screenshots if requested
                    screenshots = []
                    if take_screenshots and browser:
                        try:
                            # Take initial screenshot
                            screenshot = await browser.screenshot()
                            screenshots.append(screenshot)
                            
                            # Take additional screenshot after scrolling to verify completion
                            await browser.execute_javascript("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(1)  # Brief pause to let scrolling finish
                            screenshot_end = await browser.screenshot()
                            screenshots.append(screenshot_end)
                        except Exception as e:
                            logger.warning(f"Could not capture screenshot: {str(e)}")
                    
                    # Update progress
                    if progress_callback:
                        progress_callback("Automation completed successfully", 0.9)
                    
                    return {
                        "success": True,
                        "message": "Document successfully typed into VClass editor",
                        "screenshots": screenshots,
                        "attempt": attempts + 1  # Include attempt information
                    }
                
            except Exception as e:
                logger.error(f"Automation error (attempt {attempts+1}/{self.max_retries+1}): {str(e)}")
                attempts += 1
                
                if attempts > self.max_retries:
                    return {
                        "success": False,
                        "error": f"Automation failed after {attempts} attempts: {str(e)}"
                    }
                
                # Wait before retrying
                await asyncio.sleep(2)
        
        # Should not reach here, but just in case
        return {
            "success": False,
            "error": "Automation failed with unknown error"
        }
