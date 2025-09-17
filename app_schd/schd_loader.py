from flask import current_app
import importlib
import os
import sys
import gc

class SchdLoader:
    
    def __init__(self, module_path="handlers"):
        self.module_path = module_path
        
  
        
    def convert_module_name_to_class(self,input_string):
        # Step 1: Get the basename (last part of the path) in a cross-platform way
        after_slash = os.path.basename(input_string)
        
        # Step 2: Replace '_' with spaces
        words = after_slash.replace('_', ' ')
        
        # Step 3: Capitalize the first letter of each word
        capitalized_words = words.title()
        
        # Step 4: Remove spaces
        result = capitalized_words.replace(' ', '')
        
        return result
    
        
    def discover_modules(self,module_path):
        """Recursively finds all Python modules inside the modules directory."""
        module_list = []
        print('Discovering modules')
        
        # Use os.path.join for cross-platform path construction
        path = os.path.join('_tools', module_path, 'handlers')
        
        # Resolve the absolute path first
        base_path = os.path.abspath(path)
        print(f'Searching in: {base_path}')
        
        # Check if the directory exists
        if not os.path.exists(base_path):
            print(f'Directory not found: {base_path}')
            return module_list
        
        for root, _, files in os.walk(base_path):
            for file in files:
                print(f'File:{file}')
                if file.endswith(".py") and file != "__init__.py":
                    print(f'File ok')
                    # Convert file path into a module path (e.g., "social.create_post")
                    module_relative_path = os.path.relpath(root, base_path)  # Use base_path instead
                    module_name = file[:-3]  # Remove .py extension

                    if module_relative_path == ".":
                        full_module_path = module_name  # Top-level module
                    else:
                        # Use os.path.normpath to handle path separators properly
                        normalized_path = os.path.normpath(module_relative_path)
                        # Replace path separators with dots for module notation
                        full_module_path = f"{normalized_path.replace(os.sep, '.')}.{module_name}"

                    module_list.append(full_module_path)
        return module_list
    


    def discover_modules_x(self):
        """Recursively finds all Python modules inside the modules directory."""
        module_list = []
        print('Discovering modules')
        
        # Resolve the absolute path first
        base_path = os.path.abspath(self.module_path)
        
        # Check if the directory exists
        if not os.path.exists(base_path):
            print(f'Directory not found: {base_path}')
            return module_list
        
        for root, _, files in os.walk(base_path):
            
            for file in files:
                print(f'File:{file}')
                if file.endswith(".py") and file != "__init__.py":
                    print(f'File ok')
                    # Convert file path into a module path (e.g., "social.create_post")
                    module_relative_path = os.path.relpath(root, base_path)  # Get relative path from base folder
                    module_name = file[:-3]  # Remove .py extension

                    if module_relative_path == ".":
                        full_module_path = module_name  # Top-level module
                    else:
                        # Use os.path.normpath to handle path separators properly
                        normalized_path = os.path.normpath(module_relative_path)
                        # Replace path separators with dots for module notation
                        full_module_path = f"{normalized_path.replace(os.sep, '.')}.{module_name}"

                    module_list.append(full_module_path)
        return module_list

    def load_code_class(self,module_path, module_name, class_name, *args, **kwargs):
        """Dynamically loads a class from a module and returns an instance with provided arguments."""
        modules = self.discover_modules(module_path)
        if module_name not in modules:
            current_app.logger.debug(modules)
            current_app.logger.error(f"Module {module_name}:{class_name} not found.")
            return None
        else:
            current_app.logger.debug(f"Module {module_name}:{class_name} was found.")
        
        try:
            # Add parent directory to sys.path in a cross-platform way
            # Get the directory containing this file, then go up one level
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_file_dir)
            if parent_dir not in sys.path:
                sys.path.append(parent_dir)
            
            # Convert file path to module path format (using dots)
            module_path = f"_tools.{module_path}.handlers.{module_name}"
            
            print(f'Loading module:{module_path}')
            module = importlib.import_module(module_path)
            
            print(f'Getting class:{class_name}')
            class_ = getattr(module, class_name)
            print(f'Class created')
            return class_()
            
        
        except ModuleNotFoundError as e:
            current_app.logger.error(f"Module not found:: '{module_name}': {e}")
            return None
        except AttributeError as e:
            current_app.logger.error(f"Class '{class_name}' not found in module '{module_name}': {e}")
            return None
        except TypeError as e:
            current_app.logger.error(f"Type error when loading class '{class_name}' from '{module_name}': {e}")
            return None
        
        

    def load_and_run(self, module_name, *args, **kwargs):
        """Loads a module, runs its class method, then unloads it."""
        action = "load_and_run"
        print(f'running: {action}')
        
        try:
     
            class_name = self.convert_module_name_to_class(module_name)
            print(f'Attempting to load class:{class_name}')
            
            # Handle both file paths and dot-notation module names
            if os.sep in module_name or '/' in module_name:
                # It's a file path - normalize and split using os.sep
                normalized_module_name = os.path.normpath(module_name)
                module_parts = normalized_module_name.split(os.sep)
            else:
                # It's already in dot notation - split by dots
                module_parts = module_name.split('.')
            
            payload = kwargs.get('payload')  # Extract payload from kwargs
            
            # Ensure we have at least 2 parts for module_path and module_name
            if len(module_parts) < 2:
                error = f"Module name '{module_name}' must have at least 2 parts (module_path.module_name)"
                return {'success':False,'action':action,'error':error,'output':error,'status':500}
            
            instance = self.load_code_class(module_parts[0], module_parts[1], class_name, *args, **kwargs)
            runtime_loaded_class = True
    
            if not instance:
                error = f"Class '{class_name}' in '{module_name}' could not be loaded."
                return {'success':False,'action':action,'error':error,'output':error,'status':500}
            
            print(f'Class Loaded:{class_name}')
            
            if hasattr(instance, "run"):       
                result = instance.run(payload)  # Pass payload to run
            else:
                error = f"Class '{class_name}' in '{module_name}' has no 'run' method."
                print(error)
                return {'success':False,'action':action,'error':error,'status':500}


            if runtime_loaded_class:
                # Unload module to free memory
                del instance
                if module_name in sys.modules:
                    del sys.modules[module_name]
                gc.collect()
                
                
            
            if 'success' in result and not result['success']:
                
                return {'success':False,'action':action,'output':result,'status':400} 
            
            return {'success':True,'action':action,'output':result,'status':200}
        
        except Exception as e:
            print(f'Error @load_and_run: {str(e)}')
            return {'success':False,'action':action,'input':class_name,'output':f'Error @load_and_run: {str(e)}'}



# Example Usage
if __name__ == "__main__":
    SHL = SchdLoader()

    