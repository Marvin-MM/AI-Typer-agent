import os
import time
import sys
import asyncio
from typing import List, Optional, Dict, Any, Tuple
import re
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from dotenv import load_dotenv
import traceback
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Controller as KeyboardController, Key
import logging
from difflib import SequenceMatcher
import pyperclip
import pypandoc

from models import DocumentContent, RetypedDocument
from typer import RealKeyboardTyper

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentError(BaseModel):
    """Class to store document error information"""
    position: int
    expected: str
    actual: str
    context: str = ""
    
class VerificationResult(BaseModel):
    """Class to store document verification results"""
    match_percentage: float
    errors: List[DocumentError] = []
    success: bool = False
    
    @property
    def is_successful(self):
        """Return True if match percentage is above 99%"""
        return self.match_percentage >= 99.0 and len(self.errors) == 0

class DocumentRetyper:
    """Class to retype documents with real keyboard typing"""
    def __init__(self):
        self.document_retyper = None
        self.keyboard_typer = RealKeyboardTyper(delay=0.02)  # Increased delay for stability
        self.keyboard = KeyboardController()
        self.mouse = MouseController()
        self.original_content = ""
        self.retyped_content = ""
        self.max_chunk_size = 500  # Type in smaller chunks to prevent freezing
        self.chunk_pause = 0.5  # Pause between chunks
        
    async def async_init(self):
        """Async initialization method"""
        self.document_retyper = Agent(
            'groq:llama-3.3-70b-versatile',
            result_type=RetypedDocument,
            system_prompt=(
                "You are a document retyper assistant. Your task is to carefully read and retype"
                " documents, preserving their exact original format and content. "
                "BOLD AND ITALIC TEXT SHOULD BE PRESERVED. "
                 "For formatting, use the following markers:"
            " **bold text** for bold,"
            " __underlined text__ for underline,"
            " _italic text_ for italic."
            "use the addition functions like the ""addition"" function like toggle_bold, toggle_underline,toggle_italic "
                "USE THE REQUIRED TOOLS TO MAKE A CLEAR PROGRESS AND FASTER ERROR FREE RETYPING."
                "BULLETS, NUMBERING LIKE 1.2.3 ETC, AND PARAGRAPH SPACING SHOULD BE PRESERVED."
                "TYPE EXACT HOW THE DOCUMENT IS NO MORE STAFF ADDED IN IT AND BE CAREFUL."
                "Do not analyze, summarize, or modify the document in any way. Do not skip empty lines"
                " or spaces. Simply reproduce the document exactly as provided, maintaining all"
                "formatting, HEADINGS, bullet points, paragraph breaks, and structure."
                "Make sure that the Numbering and Bullet Points are preserved. And also incase ` is used in the document"
                " Make sure to preserve all newlines and paragraph spacing exactly as in the original."
            ),
        )
        return self

    async def navigate_to_position(self, position: int, max_pos: Optional[int] = None):
        """Navigate cursor to specific position in document with improved reliability"""
        # First go to start of document
        self.keyboard.press(Key.ctrl)
        self.keyboard.press(Key.home)
        self.keyboard.release(Key.home)
        self.keyboard.release(Key.ctrl)
        await asyncio.sleep(0.3)  # Increased delay for stability
        
        # Now move right the required number of characters with more controlled navigation
        actual_pos = min(position, max_pos or 50000)  # Lower default limit for safety
        
        # Use smaller step sizes for more reliable navigation
        remaining_steps = actual_pos
        
        # Use paragraph jumping first (Ctrl+Down) for large distances
        if remaining_steps > 500:
            jumps = min(remaining_steps // 100, 20)  # Limited to 20 paragraph jumps
            for _ in range(jumps):
                self.keyboard.press(Key.ctrl)
                self.keyboard.press(Key.down)
                self.keyboard.release(Key.down)
                self.keyboard.release(Key.ctrl)
                await asyncio.sleep(0.1)
            remaining_steps -= (jumps * 100)  # Approximate characters per paragraph
        
        # Use word jumps for medium distances (Ctrl+Right)
        if remaining_steps > 50:
            jumps = min(remaining_steps // 5, 40)  # Limited to 40 word jumps
            for _ in range(jumps):
                self.keyboard.press(Key.ctrl)
                self.keyboard.press(Key.right)
                self.keyboard.release(Key.right)
                self.keyboard.release(Key.ctrl)
                await asyncio.sleep(0.05)
            remaining_steps -= (jumps * 5)  # Approximate characters per word
        
        # Use character steps for final precision
        # Move in smaller batches with pauses to prevent input buffer overload
        while remaining_steps > 0:
            steps = min(remaining_steps, 20)  # Move maximum 20 characters at once
            for _ in range(steps):
                self.keyboard.press(Key.right)
                self.keyboard.release(Key.right)
                await asyncio.sleep(0.01)
            remaining_steps -= steps
            await asyncio.sleep(0.05)  # Small pause between batches

    async def select_text(self, length: int, max_length: Optional[int] = None):
        """Select specified number of characters with improved reliability"""
        actual_length = min(length, max_length or 5000)  # Lower default max for safety
        
        self.keyboard.press(Key.shift)
        
        # Select in smaller batches with pauses
        remaining = actual_length
        while remaining > 0:
            batch_size = min(remaining, 20)  # Select at most 20 chars at once
            for _ in range(batch_size):
                self.keyboard.press(Key.right)
                self.keyboard.release(Key.right)
                await asyncio.sleep(0.01)
            remaining -= batch_size
            await asyncio.sleep(0.05)  # Small pause between batches
            
        self.keyboard.release(Key.shift)
        await asyncio.sleep(0.2)  # Longer pause after selection
    
    async def delete_and_type(self, text: str):
        """Delete selected text and type new text with improved reliability"""
        # Delete selected text
        self.keyboard.press(Key.delete)
        self.keyboard.release(Key.delete)
        await asyncio.sleep(0.2)
        
        # Type new text in smaller chunks to prevent freezing
        remaining_text = text
        while remaining_text:
            chunk = remaining_text[:50]  # Type 50 chars at a time
            remaining_text = remaining_text[50:]
            
            for char in chunk:
                self.keyboard.press(char)
                self.keyboard.release(char)
                await asyncio.sleep(0.02)  # Slightly slower typing for stability
                
            await asyncio.sleep(0.1)  # Pause between chunks
    
    async def select_all_and_copy(self):
        """Select all text and copy to clipboard with improved reliability"""
        # Try multiple times in case of failure
        for attempt in range(3):
            try:
                # Clear clipboard first
                pyperclip.copy('')
                await asyncio.sleep(0.2)
                
                # Select all text
                self.keyboard.press(Key.ctrl)
                self.keyboard.press('a')
                self.keyboard.release('a')
                self.keyboard.release(Key.ctrl)
                await asyncio.sleep(0.5)  # Longer pause for large documents
                
                # Copy to clipboard
                self.keyboard.press(Key.ctrl)
                self.keyboard.press('c')
                self.keyboard.release('c')
                self.keyboard.release(Key.ctrl)
                await asyncio.sleep(0.5)  # Longer pause for clipboard operation
                
                # Get clipboard content
                result = pyperclip.paste()
                if result:
                    return result
                    
                print(f"Copy attempt {attempt+1} failed. Retrying...")
                await asyncio.sleep(1)  # Wait before retry
                
            except Exception as e:
                print(f"Error during copy operation (attempt {attempt+1}): {str(e)}")
                await asyncio.sleep(1)  # Wait before retry
        
        print("Failed to copy content after multiple attempts")
        return ""  # Return empty string if all attempts fail
    
    async def find_all_errors(self, original: str, typed: str, max_errors: int = 20) -> List[DocumentError]:
        """Find all errors between original and typed content with a limit and improved accuracy"""
        errors = []
        
        # For very large documents, use difflib for more efficient comparison
        if len(original) > 10000 or len(typed) > 10000:
            print("Large document detected. Using efficient diff algorithm...")
            import difflib
            matcher = difflib.SequenceMatcher(None, original, typed)
            
            # Process diff blocks
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag != 'equal' and len(errors) < max_errors:
                    # Found a difference
                    context_start = max(0, j1 - 10)
                    context_end = min(j2 + 10, len(typed))
                    
                    errors.append(DocumentError(
                        position=j1,
                        expected=original[i1:i2],
                        actual=typed[j1:j2],
                        context=f"...{typed[context_start:context_end]}..."
                    ))
        else:
            # For smaller documents, use character-by-character comparison
            min_len = min(len(original), len(typed))
            position = 0
            error_start = -1
            
            while position < min_len and len(errors) < max_errors:
                if original[position] != typed[position]:
                    # Start of an error
                    if error_start == -1:
                        error_start = position
                elif error_start != -1:
                    # End of an error
                    context_start = max(0, error_start - 10)
                    context_end = min(position + 10, min_len)
                    
                    errors.append(DocumentError(
                        position=error_start,
                        expected=original[error_start:position],
                        actual=typed[error_start:position],
                        context=f"...{typed[context_start:context_end]}..."
                    ))
                    error_start = -1
                position += 1
            
            # Handle error at end of document
            if error_start != -1 and len(errors) < max_errors:
                errors.append(DocumentError(
                    position=error_start,
                    expected=original[error_start:min_len],
                    actual=typed[error_start:min_len],
                    context=f"...{typed[max(0, error_start-10):min_len]}"
                ))
        
        # Check for length differences
        if len(original) > len(typed) and len(errors) < max_errors:
            # Missing content at the end
            errors.append(DocumentError(
                position=len(typed),
                expected=original[len(typed):len(typed)+20] + "..." if len(original) - len(typed) > 20 else original[len(typed):],
                actual="",
                context="[End of document - missing content]"
            ))
        elif len(typed) > len(original) and len(errors) < max_errors:
            # Extra content at the end
            errors.append(DocumentError(
                position=len(original),
                expected="",
                actual=typed[len(original):len(original)+20] + "..." if len(typed) - len(original) > 20 else typed[len(original):],
                context="[End of document - extra content]"
            ))
        
        if len(errors) >= max_errors:
            print(f"Warning: Found {max_errors}+ errors. Limiting to first {max_errors} for performance.")
            
        return errors
    
    async def auto_fix_errors(self, errors: List[DocumentError], doc_length: int):
        """Automatically fix all identified errors with improved reliability"""
        print(f"\nFixing {len(errors)} errors automatically...")
        
        # Sort errors by position in descending order (fix from end to start)
        sorted_errors = sorted(errors, key=lambda x: x.position, reverse=True)
        
        # Limit number of errors fixed in one session to prevent freezing
        max_fixes_per_session = 10
        for batch_idx in range(0, len(sorted_errors), max_fixes_per_session):
            current_batch = sorted_errors[batch_idx:batch_idx + max_fixes_per_session]
            print(f"Processing error batch {batch_idx // max_fixes_per_session + 1}/{(len(sorted_errors) + max_fixes_per_session - 1) // max_fixes_per_session}...")
            
            for i, error in enumerate(current_batch):
                print(f"Fixing error {batch_idx + i + 1}/{len(sorted_errors)} at position {error.position}...")
                
                # Add safety checks
                if error.position >= doc_length:
                    print(f"  Skipping - position {error.position} exceeds document length {doc_length}")
                    continue
                    
                try:
                    # Navigate to error position with safeguard
                    await self.navigate_to_position(error.position, doc_length)
                    
                    # Select the error text with safeguard
                    error_length = len(error.actual) if error.actual else 0
                    await self.select_text(error_length, doc_length - error.position)
                    
                    # Replace with correct text
                    await self.delete_and_type(error.expected)
                    
                    # Longer pause between operations
                    await asyncio.sleep(0.3)
                except Exception as e:
                    print(f"  Error during fix: {str(e)}")
                    # Continue with next error
            
            # Longer pause between batches to prevent freezing
            print(f"Finished batch. Pausing to allow system to stabilize...")
            await asyncio.sleep(2.0)
            
        # Ensure cursor is reset to a safe position (start of document)
        self.keyboard.press(Key.ctrl)
        self.keyboard.press(Key.home)
        self.keyboard.release(Key.home)
        self.keyboard.release(Key.ctrl)
        await asyncio.sleep(0.5)
            
        print("All errors fixed automatically!")
    
    async def verify_document(self, original_content: str) -> VerificationResult:
        """Verify document against original and return result (separate function for external calls)"""
        print("\n=== Starting Document Verification ===")
        print("1. Selecting all text and copying to analyze...")
        
        # Get current document content
        current_content = await self.select_all_and_copy()
        self.retyped_content = current_content
        
        # Calculate similarity
        similarity = SequenceMatcher(None, original_content, current_content).ratio() * 100
        print(f"Document similarity: {similarity:.2f}%")
        
        # Find all errors (with reduced limit for performance)
        print("2. Analyzing for errors...")
        errors = await self.find_all_errors(original_content, current_content, max_errors=20)
        
        # Create verification result
        result = VerificationResult(
            match_percentage=similarity,
            errors=errors,
            success=(not errors and similarity >= 99.0)
        )
        
        # Report errors
        if not result.success:
            print(f"\nFound {len(errors)} errors:")
            for i, error in enumerate(errors[:5]):  # Show first 5 errors only
                print(f"  Error {i+1}: Position {error.position}")
                print(f"    Expected: '{error.expected}'")
                print(f"    Actual:   '{error.actual}'")
                print(f"    Context:  {error.context}")
            
            if len(errors) > 5:
                print(f"  ... and {len(errors) - 5} more errors")
        else:
            print("✓ Verification complete - document is perfect!")
        
        # Reset cursor position to beginning
        self.keyboard.press(Key.ctrl)
        self.keyboard.press(Key.home)
        self.keyboard.release(Key.home)
        self.keyboard.release(Key.ctrl)
        
        return result
    
    async def verify_and_correct_document(self, original_content: str):
        """Verify document against original and fix any errors"""
        result = await self.verify_document(original_content)
        
        if result.success:
            return True
        
        # Auto-fix errors
        doc_length = len(self.retyped_content)
        await self.auto_fix_errors(result.errors, doc_length)
        
        # Verify again
        print("\nVerifying fixes...")
        final_result = await self.verify_document(original_content)
        
        if final_result.success:
            print("✓ All errors successfully fixed!")
            return True
        else:
            print("⚠ Some errors may remain.")
            if len(final_result.errors) <= 5:  # If only a few errors remain, try one more fix
                print("Attempting final fix for remaining errors...")
                await self.auto_fix_errors(final_result.errors, doc_length)
                # Final check
                last_result = await self.verify_document(original_content)
                if last_result.success:
                    print("✓ All errors resolved in final pass!")
                    return True
            
            print("Consider running verification again.")
            return False
    
    async def apply_formatting(self, formatting_elements, doc_length: int):
        """Apply formatting to the document with improved reliability"""
        print("\n=== Applying Document Formatting ===")
        
        # Process formatting types one by one
        for fmt_type, positions in formatting_elements.items():
            if not positions:
                continue
                
            print(f"Applying {fmt_type} formatting to {len(positions)} elements...")
            
            # Limit number of formatting operations per batch
            max_items_per_batch = 10
            for batch_idx in range(0, len(positions), max_items_per_batch):
                current_batch = positions[batch_idx:batch_idx + max_items_per_batch]
                print(f"Processing {fmt_type} batch {batch_idx // max_items_per_batch + 1}/{(len(positions) + max_items_per_batch - 1) // max_items_per_batch}...")
                
                for idx, (start, end, text) in enumerate(current_batch):
                    # Add safety check
                    if start >= doc_length or end > doc_length:
                        print(f"  Skipping formatting '{text[:20]}...' - position out of bounds")
                        continue
                        
                    try:
                        print(f"  Formatting '{text[:20]}...'")
                        
                        # Navigate to position with safeguard
                        await self.navigate_to_position(start, doc_length)
                        
                        # Select text with safeguard
                        await self.select_text(end - start, doc_length - start)
                        
                        # Apply formatting
                        self.keyboard.press(Key.ctrl)
                        
                        if fmt_type == "bold":
                            self.keyboard.press('b')
                            self.keyboard.release('b')
                        elif fmt_type == "italic":
                            self.keyboard.press('i')
                            self.keyboard.release('i')
                        elif fmt_type == "underline":
                            self.keyboard.press('u')
                            self.keyboard.release('u')
                        
                        self.keyboard.release(Key.ctrl)
                        await asyncio.sleep(0.3)  # Longer pause between formatting operations
                    except Exception as e:
                        print(f"  Error during formatting: {str(e)}")
                        # Continue with next formatting
                
                # Pause between batches
                await asyncio.sleep(1.0)
        
        # Reset cursor position to beginning
        self.keyboard.press(Key.ctrl)
        self.keyboard.press(Key.home)
        self.keyboard.release(Key.home)
        self.keyboard.release(Key.ctrl)
        
        print("Formatting complete!")
    
    async def extract_formatting_elements(self, content: str):
        """Extract formatting elements from markdown-style formatting"""
        formatting = {
            "bold": [],       # (start_pos, end_pos, text)
            "italic": [],     # (start_pos, end_pos, text)
            "underline": []   # (start_pos, end_pos, text)
        }
        
        # Find bold text (**text**)
        bold_pattern = re.compile(r'\*\*(.*?)\*\*')
        for match in bold_pattern.finditer(content):
            start = match.start()
            end = match.end()
            text = match.group(1)
            # Calculate position without markers
            clean_content = re.sub(r'\*\*(.*?)\*\*', r'\1', content[:start])
            clean_pos = len(clean_content)
            formatting["bold"].append((clean_pos, clean_pos + len(text), text))
        
        # Find italic text (_text_)
        italic_pattern = re.compile(r'_(.*?)_')
        for match in italic_pattern.finditer(content):
            start = match.start()
            end = match.end()
            text = match.group(1)
            # Calculate position without markers
            clean_content = re.sub(r'_(.*?)_', r'\1', content[:start])
            clean_content = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_content)
            clean_pos = len(clean_content)
            formatting["italic"].append((clean_pos, clean_pos + len(text), text))
        
        # Find underline text (__text__)
        underline_pattern = re.compile(r'__(.*?)__')
        for match in underline_pattern.finditer(content):
            start = match.start()
            end = match.end()
            text = match.group(1)
            # Calculate position without markers
            clean_content = re.sub(r'__(.*?)__', r'\1', content[:start])
            clean_content = re.sub(r'_(.*?)_', r'\1', clean_content)
            clean_content = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_content)
            clean_pos = len(clean_content)
            formatting["underline"].append((clean_pos, clean_pos + len(text), text))
        
        return formatting
    
    async def prepare_clean_content(self, content: str):
        """Remove formatting markers from content"""
        clean = content
        clean = re.sub(r'\*\*(.*?)\*\*', r'\1', clean)  # Remove bold markers
        clean = re.sub(r'_(.*?)_', r'\1', clean)        # Remove italic markers
        clean = re.sub(r'__(.*?)__', r'\1', clean)      # Remove underline markers
        return clean

    async def retype_document_with_real_typing(self, document_text: str, typing_position=None):
        """Function to retype a document using real keyboard inputs with improved chunking and reliability"""
        content = DocumentContent(text=document_text)
        self.original_content = document_text
        
        # Extract formatting elements before removing markers
        formatting_elements = await self.extract_formatting_elements(document_text)
        
        # Prepare clean content (without formatting markers)
        clean_content = await self.prepare_clean_content(document_text)
        
        # Show information
        print(f"Reading document content...")
        print(f"Document has {len(clean_content)} characters")
        print(f"Found formatting: {sum(len(elements) for elements in formatting_elements.values())} elements")
        
        # Process the document with the agent
        try:
            result = await self.document_retyper.run(
                f"Please retype the following document exactly as it is, preserving all formatting, spacing,"
                f" line breaks, and paragraph structure: {content.text}"
            )
        except Exception as e:
            print(f"Warning: Agent processing error: {str(e)}")
            print("Proceeding with direct typing of clean content...")
        
        # Prepare user for typing
        print(f"Preparing to type the document with real keyboard inputs.")
        print(f"Please open the target file/editor and place your cursor where typing should begin.")
        print(f"You have 5 seconds to get ready...")
        
        # Countdown
        for i in range(5, 0, -1):
            print(f"{i}...")
            await asyncio.sleep(1)
        
        print("Typing now! Will type document in smaller chunks to prevent freezing...")
        
        # Type in smaller chunks to prevent freezing
        total_chunks = (len(clean_content) + self.max_chunk_size - 1) // self.max_chunk_size
        
        try:
            # First type the content in chunks
            for i in range(total_chunks):
                chunk_start = i * self.max_chunk_size
                chunk_end = min((i + 1) * self.max_chunk_size, len(clean_content))
                chunk = clean_content[chunk_start:chunk_end]
                
                print(f"Typing chunk {i+1}/{total_chunks} ({len(chunk)} characters)...")
                
                # Type this chunk
                await self.keyboard_typer.type_with_verification(chunk, typing_position, True)
                
                # Pause between chunks to let system catch up
                print(f"Chunk {i+1} complete. Pausing...")
                await asyncio.sleep(self.chunk_pause)
                
                # Reset typing position to None after first chunk
                typing_position = None
                
            print(f"\nDocument content typed successfully!")
            
            # Now verify the document
            print("\nVerifying document content...")
            success = await self.verify_and_correct_document(clean_content)
            
            if success:
                # Apply formatting if needed
                if sum(len(elements) for elements in formatting_elements.values()) > 0:
                    print("\nApplying document formatting...")
                    await self.apply_formatting(formatting_elements, len(clean_content))
                
                print(f"\nDocument successfully retyped and verified!")
            else:
                print("\nDocument verification showed issues. Consider running verification separately.")
            
        except Exception as e:
            print(f"Error during typing: {str(e)}")
            traceback.print_exc()
        
        # Ensure cursor is reset to a safe position
        self.keyboard.press(Key.ctrl)
        self.keyboard.press(Key.home)
        self.keyboard.release(Key.home)
        self.keyboard.release(Key.ctrl)
        
        return clean_content
    
