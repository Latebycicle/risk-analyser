"""
Financial Compliance Checker Module

This module provides functions to check if planned billing dates
comply with contractual timeline rules using Ollama with local AI models.

Usage:
    from src.compliance_checker import check_contractual_timeline
    
    result = check_contractual_timeline("2025-09-01", "Advance")
    print(result)  # {'at_risk': False, 'reasoning': '...'}
"""

import json
import logging
import sys
from typing import Dict, Any
from pathlib import Path

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.settings import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
except ImportError:
    OLLAMA_URL = "http://localhost:11434/api/generate"
    OLLAMA_MODEL = "qwen3:4b"
    OLLAMA_TIMEOUT = 300

import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def call_ollama_api(prompt: str) -> str:
    """
    Call the Ollama API with the configured model.
    
    Args:
        prompt: The prompt to send to the LLM
        
    Returns:
        The LLM's response as a string
    """
    schema = {
        "type": "object",
        "properties": {
            "at_risk": {"type": "boolean"},
            "reasoning": {"type": "string"}
        },
        "required": ["at_risk", "reasoning"]
    }
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": schema,
        "think": False,
        "keep_alive": "5m",
        "options": {
            "temperature": 0.0,
            "num_ctx": 2048
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        
        result = response.json()
        return result.get("response", "")
        
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Could not connect to Ollama. Make sure Ollama is running."
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Ollama request timed out after {OLLAMA_TIMEOUT} seconds.")
    except Exception as e:
        logging.error(f"Error calling Ollama API: {e}")
        raise


def check_contractual_timeline(planned_date: str, contractual_rule: str) -> Dict[str, Any]:
    """
    Check if a planned billing date violates a contractual timeline rule.
    
    Args:
        planned_date: The internal date expected to bill (e.g., "2025-09-01")
        contractual_rule: The contractual rule (e.g., "Advance", "After 6 months")
        
    Returns:
        Dictionary with keys:
            - 'at_risk' (bool): True if the date violates the rule
            - 'reasoning' (str): Brief explanation
    """
    
    prompt = f"""Analyze if this payment date violates the contractual rule. Return as JSON.

Payment Date: {planned_date}
Contractual Rule: {contractual_rule}

Determine:
- at_risk: true if the date violates the rule, false if compliant
- reasoning: brief explanation (one sentence)

Examples:
- "2025-09-01" with "Advance" → compliant
- "2025-09-02" with "After 6 months" → violation (too early)
- "2025-11-01" with "2nd Installment" → compliant"""

    try:
        response_text = call_ollama_api(prompt)
        
        # Clean response
        response_text = response_text.strip()
        
        if '</think>' in response_text:
            response_text = response_text.split('</think>')[-1].strip()
        
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start >= 0 and end > start:
                result = json.loads(response_text[start:end])
            else:
                raise
        
        # Validate response
        if 'at_risk' not in result or 'reasoning' not in result:
            raise ValueError("Missing required fields")
        
        if not isinstance(result['at_risk'], bool):
            raise ValueError("'at_risk' must be boolean")
        
        logging.info(
            f"Assessment: {planned_date} vs '{contractual_rule}' -> at_risk={result['at_risk']}"
        )
        
        return result
        
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse response: {e}")
        raise ValueError(f"Invalid JSON response: {e}")
    except Exception as e:
        logging.error(f"Compliance check error: {e}")
        raise


if __name__ == "__main__":
    print("Compliance Checker Module Test")
    print("=" * 50)
    
    test_cases = [
        ("2025-09-01", "Advance"),
        ("2025-11-01", "2nd Installment"),
        ("2026-01-01", "3rd Installment"),
    ]
    
    for planned_date, rule in test_cases:
        print(f"\nDate: {planned_date}, Rule: {rule}")
        try:
            result = check_contractual_timeline(planned_date, rule)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")
