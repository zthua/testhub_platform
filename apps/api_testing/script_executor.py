"""
Script execution utility for pre-request and post-request scripts.
Supports both Python and JavaScript execution.
"""
import json
import logging
import sys
import traceback
from typing import Dict, Any, Optional
from io import StringIO

logger = logging.getLogger(__name__)


class ScriptExecutionResult:
    """Script execution result container"""
    
    def __init__(self):
        self.success = True
        self.output = ""
        self.error = None
        self.modified_context = {}
        self.logs = []
    
    def to_dict(self):
        return {
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'modified_context': self.modified_context,
            'logs': self.logs
        }


class ScriptExecutor:
    """Script executor for Python and JavaScript scripts"""
    
    @staticmethod
    def execute_python_script(
        script_content: str,
        context: Dict[str, Any],
        timeout: int = 30
    ) -> ScriptExecutionResult:
        """
        Execute a Python script with given context.
        
        Args:
            script_content: The Python script code to execute
            context: Dictionary containing variables available to script
            timeout: Maximum execution time in seconds
            
        Returns:
            ScriptExecutionResult object containing execution results
        """
        result = ScriptExecutionResult()
        
        # Create a safe execution environment
        safe_locals = {
            '__builtins__': {
                'print': lambda *args, **kwargs: result.logs.append(' '.join(str(a) for a in args)),
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'dict': dict,
                'list': list,
                'tuple': tuple,
                'set': set,
                'json': json,
                'range': range,
                'sum': sum,
                'min': min,
                'max': max,
                'abs': abs,
                'round': round,
                'pow': pow,
            },
        }
        
        # Add context variables
        safe_locals.update(context)
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            # Execute script
            exec(script_content, safe_locals, safe_locals)
            
            # Capture any output
            result.output = captured_output.getvalue()
            
            # Check for modified context variables
            original_keys = set(context.keys())
            new_keys = set(safe_locals.keys())
            added_keys = new_keys - original_keys - set(['__builtins__'])
            
            for key in added_keys:
                result.modified_context[key] = safe_locals[key]
            
            # Also check for modified values
            for key in context.keys():
                if key in safe_locals and key != '__builtins__':
                    new_value = safe_locals[key]
                    if new_value != context[key]:
                        result.modified_context[key] = new_value
            
            result.success = True
            
        except Exception as e:
            result.success = False
            result.error = f"Script execution failed: {str(e)}"
            logger.error(f"Python script execution error: {e}\n{traceback.format_exc()}")
            
        finally:
            sys.stdout = old_stdout
        
        return result
    
    @staticmethod
    def execute_javascript_script(
        script_content: str,
        context: Dict[str, Any],
        timeout: int = 30
    ) -> ScriptExecutionResult:
        """
        Execute a JavaScript script with given context.
        
        Args:
            script_content: The JavaScript code to execute
            context: Dictionary containing variables available to script
            timeout: Maximum execution time in seconds
            
        Returns:
            ScriptExecutionResult object containing execution results
        """
        result = ScriptExecutionResult()
        
        # Try to use PyExecJS if available
        try:
            import execjs
        except ImportError:
            # Fallback: try using Node.js directly via subprocess
            try:
                return ScriptExecutor._execute_javascript_via_subprocess(
                    script_content, context, timeout
                )
            except Exception as e:
                result.success = False
                result.error = f"JavaScript execution not available. Please install execjs or ensure Node.js is installed: {str(e)}"
                logger.error(f"JavaScript execution error: {e}")
                return result
        
        try:
            # Prepare context for JavaScript
            # Convert Python types to JSON-compatible types
            js_context = json.dumps(context, ensure_ascii=False)
            
            # Wrap script to expose context and capture output
            wrapped_script = f"""
                (function() {{
                    var context = {js_context};
                    var output = [];
                    
                    // Override console.log to capture output
                    console.log = function() {{
                        output.push(Array.prototype.slice.call(arguments).join(' '));
                    }};
                    
                    // Execute user script
                    {script_content}
                    
                    // Return modified context and output
                    return {{
                        modifiedContext: context,
                        output: output.join('\\n')
                    }};
                }})();
            """
            
            # Execute JavaScript code
            ctx = execjs.get()
            js_result = ctx.eval(wrapped_script)
            
            result.output = js_result.get('output', '')
            result.modified_context = js_result.get('modifiedContext', {})
            result.success = True
            
        except Exception as e:
            result.success = False
            result.error = f"JavaScript execution failed: {str(e)}"
            logger.error(f"JavaScript execution error: {e}\n{traceback.format_exc()}")
        
        return result
    
    @staticmethod
    def _execute_javascript_via_subprocess(
        script_content: str,
        context: Dict[str, Any],
        timeout: int = 30
    ) -> ScriptExecutionResult:
        """
        Fallback method: Execute JavaScript using Node.js via subprocess.
        """
        import subprocess
        result = ScriptExecutionResult()
        
        # Prepare context for JavaScript
        js_context = json.dumps(context, ensure_ascii=False)

        # Wrap script to expose context and capture output
        # Add fetch polyfill for Node.js environment
        wrapped_script = f"""
            // Fetch polyfill for Node.js
            const https = require('https');
            const http = require('http');
            const url = require('url');

            function fetch(fullUrl, options = {{}}) {{
                return new Promise((resolve, reject) => {{
                    const urlObj = url.parse(fullUrl);
                    const isHttps = urlObj.protocol === 'https:';
                    const client = isHttps ? https : http;

                    const requestOptions = {{
                        hostname: urlObj.hostname,
                        port: urlObj.port || (isHttps ? 443 : 80),
                        path: urlObj.path,
                        method: options.method || 'GET',
                        headers: options.headers || {{}},
                        body: options.body ? options.body : undefined
                    }};

                    const req = client.request(requestOptions, (res) => {{
                        let data = '';

                        res.on('data', (chunk) => {{
                            data += chunk;
                        }});

                        res.on('end', () => {{
                            // Create headers object with get method
                            const headers = {{
                                get: (name) => {{
                                    const lowerName = name.toLowerCase();
                                    for (const [key, value] of Object.entries(res.headers)) {{
                                        if (key.toLowerCase() === lowerName) {{
                                            // Handle set-cookie as array
                                            if (lowerName === 'set-cookie') {{
                                                if (Array.isArray(value)) {{
                                                    return value[0];
                                                }}
                                                return value;
                                            }}
                                            return value;
                                        }}
                                    }}
                                    return null;
                                }},
                                entries: () => Object.entries(res.headers)
                            }};

                            resolve({{
                                ok: res.statusCode >= 200 && res.statusCode < 300,
                                status: res.statusCode,
                                headers: headers,
                                json: async () => {{
                                    try {{
                                        return JSON.parse(data);
                                    }} catch (e) {{
                                        return null;
                                    }}
                                }},
                                text: async () => data
                            }});
                        }});
                    }});

                    req.on('error', (err) => {{
                        reject(err);
                    }});

                    if (options.body) {{
                        req.write(options.body);
                    }}
                    req.end();
                }});
            }}

            (function() {{
                var context = {js_context};
                var output = [];

                // Override console.log to capture output
                console.log = function() {{
                    output.push(Array.prototype.slice.call(arguments).join(' '));
                }};

                // Execute user script
                try {{
                    {script_content}
                    console.log('---RESULT-BEGIN---');
                    console.log(JSON.stringify({{
                        modifiedContext: context,
                        output: output.join('\\n')
                    }}));
                }} catch (e) {{
                    console.log('---ERROR-BEGIN---');
                    console.log(e.message);
                    console.log(e.stack);
                }}
            }})();
        """
        
        try:
            # Run Node.js with script
            process = subprocess.run(
                ['node'],
                input=wrapped_script,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8'
            )

            output = process.stdout
            stderr = process.stderr

            logger.debug(f"Node.js returncode: {process.returncode}")
            logger.debug(f"Node.js stdout: {output[:500]}")
            if stderr:
                logger.debug(f"Node.js stderr: {stderr[:500]}")

            if process.returncode == 0 and '---RESULT-BEGIN---' in output:
                # Extract result
                _, result_part = output.split('---RESULT-BEGIN---', 1)
                js_result = json.loads(result_part.strip())

                result.output = js_result.get('output', '')
                result.modified_context = js_result.get('modifiedContext', {})
                result.success = True
            elif '---ERROR-BEGIN---' in output:
                # Extract error
                _, error_part = output.split('---ERROR-BEGIN---', 1)
                result.success = False
                result.error = f"Script error: {error_part.strip()}"
            else:
                result.success = False
                error_details = []
                if process.returncode != 0:
                    error_details.append(f"Return code: {process.returncode}")
                if output:
                    error_details.append(f"Output: {output[:500]}")
                if stderr:
                    error_details.append(f"Stderr: {stderr[:500]}")
                result.error = f"Unknown error: {'; '.join(error_details) if error_details else 'No output'}"
                
        except FileNotFoundError:
            result.success = False
            result.error = "Node.js not found. Please install Node.js or execjs package."
        except subprocess.TimeoutExpired:
            result.success = False
            result.error = f"Script execution timed out after {timeout} seconds"
        except Exception as e:
            result.success = False
            result.error = f"JavaScript execution failed: {str(e)}"
        
        return result
    
    @staticmethod
    def execute_script(
        script_type: str,
        script_content: str,
        context: Dict[str, Any],
        timeout: int = 30
    ) -> ScriptExecutionResult:
        """
        Execute a script based on its type.
        
        Args:
            script_type: 'python' or 'javascript'
            script_content: The script code to execute
            context: Dictionary containing variables available to script
            timeout: Maximum execution time in seconds
            
        Returns:
            ScriptExecutionResult object containing execution results
        """
        script_type = script_type.lower()
        
        if script_type == 'python':
            return ScriptExecutor.execute_python_script(script_content, context, timeout)
        elif script_type == 'javascript':
            return ScriptExecutor.execute_javascript_script(script_content, context, timeout)
        else:
            result = ScriptExecutionResult()
            result.success = False
            result.error = f"Unsupported script type: {script_type}"
            return result
