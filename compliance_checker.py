"""
Financial Compliance Checker Module

This module provides functions to check if planned billing dates
comply with contractual timeline rules using Ollama with qwen3:4b.
"""

import json
import logging
from typing import Dict, Any
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def call_ollama_api(prompt: str, model: str = "qwen3:4b") -> str:
    """
    Call the Ollama API with the specified model.
    
    Args:
        prompt: The prompt to send to the LLM
        model: The Ollama model to use (default: qwen3:4b)
        
    Returns:
        The LLM's response as a string
        
    Raises:
        requests.RequestException: If the API call fails
    """
    ollama_url = "http://localhost:11434/api/generate"
    
    # Define JSON schema for structured output
    schema = {
        "type": "object",
        "properties": {
            "at_risk": {
                "type": "boolean"
            },
            "reasoning": {
                "type": "string"
            }
        },
        "required": ["at_risk", "reasoning"]
    }
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": schema,  # Use structured output with JSON schema
        "think": False,  # Critical: Disable thinking for fast responses
        "keep_alive": "5m",
        "options": {
            "temperature": 0.0,
            "num_ctx": 2048
        }
    }
    
    try:
        logging.debug(f"Calling Ollama API with model: {model}")
        response = requests.post(ollama_url, json=payload, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        return result.get("response", "")
        
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Could not connect to Ollama. Make sure Ollama is running "
            "(start it with 'ollama serve' or the Ollama app)."
        )
    except requests.exceptions.Timeout:
        raise TimeoutError("Ollama API request timed out after 300 seconds.")
    except Exception as e:
        logging.error(f"Error calling Ollama API: {e}")
        raise


def check_contractual_timeline(planned_date: str, contractual_rule: str) -> Dict[str, Any]:
    """
    Check if a planned billing date violates a contractual timeline rule.
    
    This function uses Ollama with qwen3:4b to analyze whether the planned date
    is consistent with the contractual rule, acting as a strict financial
    compliance auditor.
    
    Args:
        planned_date: The internal date expected to bill (e.g., "2025-09-01")
        contractual_rule: The messy contractual rule (e.g., "Advance", "2nd Installment")
        
    Returns:
        Dictionary with keys:
            - 'at_risk' (bool): True if the planned date violates the rule
            - 'reasoning' (str): Brief explanation of the assessment
            
    Example:
        >>> result = check_contractual_timeline("2025-09-01", "Advance")
        >>> print(result)
        {'at_risk': False, 'reasoning': 'The planned date is consistent with...'}
    """
    
    # Construct prompt for structured output
    prompt = f"""Analyze if this payment date violates the contractual rule. Return as JSON.

Payment Date: {planned_date}
Contractual Rule: {contractual_rule}

Determine:
- at_risk: true if the date violates the rule, false if compliant
- reasoning: brief explanation (one sentence)

Examples:
- Date "2025-09-01" with rule "Advance" → compliant (advance payment at project start)
- Date "2025-09-02" with rule "After 6 months" → violation (too early, needs 6 months)
- Date "2025-11-01" with rule "2nd Installment" → compliant (reasonable timing for 2nd payment)

Analyze the payment date and contractual rule above."""

    try:
        # Call the Ollama API
        logging.debug(f"Checking: {planned_date} against '{contractual_rule}'")
        response_text = call_ollama_api(prompt)
        
        # Parse the JSON response
        # Remove markdown code blocks and thinking tags if present
        response_text = response_text.strip()
        
        # Handle models that output thinking even when think=False
        if '</think>' in response_text:
            # Extract content after </think> tag
            response_text = response_text.split('</think>')[-1].strip()
        
        # Remove markdown formatting
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON with fallback
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback: extract JSON object from text
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start >= 0 and end > start:
                json_text = response_text[start:end]
                result = json.loads(json_text)
            else:
                raise
        
        # Validate the response structure
        if 'at_risk' not in result or 'reasoning' not in result:
            logging.error(f"LLM response missing required fields. Got: {result}")
            raise ValueError("LLM response missing required fields 'at_risk' or 'reasoning'")
        
        if not isinstance(result['at_risk'], bool):
            raise ValueError("'at_risk' field must be a boolean")
        
        logging.info(
            f"Assessment: {planned_date} vs '{contractual_rule}' -> "
            f"at_risk={result['at_risk']}"
        )
        
        return result
        
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse LLM response as JSON: {e}")
        logging.error(f"Response text: {response_text}")
        raise ValueError(f"LLM returned invalid JSON: {e}")
    
    except Exception as e:
        logging.error(f"Error during compliance check: {e}")
        raise


if __name__ == "__main__":
    # Example usage and testing
    print("Compliance Checker Module (Ollama with qwen3:4b)")
    print("=" * 50)
    
    # Test cases
    test_cases = [
        ("2025-09-01", "Advance"),
        ("2025-11-01", "2nd Installment"),
        ("2026-01-01", "3rd Installment"),
    ]
    
    print("\nTest cases:")
    print("Make sure Ollama is running with the qwen3:4b model\n")
    
    for planned_date, contractual_rule in test_cases:
        print(f"\nPlanned Date: {planned_date}")
        print(f"Contractual Rule: {contractual_rule}")
        try:
            result = check_contractual_timeline(planned_date, contractual_rule)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")
