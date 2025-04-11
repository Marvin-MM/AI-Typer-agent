import os
import time
import sys
import asyncio
from typing import List, Optional, Dict, Any
import re
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from dotenv import load_dotenv
import traceback
import random
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController
import pyautogui
import keyboard
import language_tool_python
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    langage_tool = language_tool_python.LanguageTool('en-US')
except Exception as e:
    logging.warning(f"Warning: Error initializing language tool: {e}")
    langage_tool = None
if langage_tool:
    logging.debug("Success: Language tool initialized successfully.")


class GrammarChecker:
    """Class to check grammar and provide corrections"""
    
    def __init__(self):
        self.language_tool = langage_tool
    
    def check_grammar(self, text: str) -> List[Dict]:
        """Check grammar and return corrections"""
        if not self.language_tool:
            return []
        
        # It gets matches from language tool
        matches = self.language_tool.check(text)
        
        corrections = []
        for match in matches:
            if match.replacements:
                corrections.append({
                    "type": "grammar",
                    "message": match.message,
                    "offset": match.offset,
                    "length": match.errorLength,
                    "replacements": match.replacements,
                    "rule_id": match.ruleId
                })
        
        return corrections
    
    def apply_correction(self, text: str, correction: Dict) -> str:
        """Apply a single correction to the text"""
        if correction["type"] == "grammar" and correction["replacements"]:
            # Replaces the text at the given offset with the first suggestion
            offset = correction["offset"]
            length = correction["length"]
            replacement = correction["replacements"][0]
            
            return text[:offset] + replacement + text[offset + length:]
        
        return text

#Helper for Document verification
class DocumentVerifier:
    """Class to verify document content and detect errors"""
    def __init__(self):
        pass
    
    def compare_content(self, original: str, typed: str) -> Dict[str, Any]:
        """Compare original content with typed content to detect errors"""
        # Split into lines for comparison
        original_lines = original.split('\n')
        typed_lines = typed.split('\n')
        
        errors = []
        
        # Check length difference first
        if len(original_lines) != len(typed_lines):
            errors.append({
                "type": "line_count_mismatch",
                "message": f"Line count mismatch: {len(original_lines)} vs {len(typed_lines)}"
            })
        
        # Compare line by line
        for i, (orig, typed) in enumerate(zip(original_lines, typed_lines[:len(original_lines)])):
            if orig != typed:
                # Find the position of the first difference
                pos = next((j for j in range(min(len(orig), len(typed))) if orig[j] != typed[j]), min(len(orig), len(typed)))
                errors.append({
                    "type": "content_mismatch",
                    "line": i + 1,
                    "position": pos + 1,
                    "original": orig,
                    "typed": typed
                })
        
        return {
            "match": len(errors) == 0,
            "errors": errors
        }

#Helper for RealKeyboard Typing
