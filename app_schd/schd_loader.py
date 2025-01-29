from flask import current_app
import importlib
import os
import sys
import gc


class SchdLoader:
    
    def __init__(self, module_path="handlers"):
        self.module_path = module_path
        #self.OPG = OperateGame()
        #self.modules = self.discover_modules()
        

    def discover_modules(self):
        """Recursively finds all Python modules inside the modules directory."""
        module_list = []
        print('Discovering modules')
        
        for root, _, files in os.walk(self.module_path):
            
            for file in files:
                print(f'File:{file}')
                if file.endswith(".py") and file != "__init__.py":
                    print(f'File ok')
                    # Convert file path into a module path (e.g., "social.create_post")
                    module_relative_path = os.path.relpath(root, self.module_path)  # Get relative path from base folder
                    module_name = file[:-3]  # Remove .py extension

                    if module_relative_path == ".":
                        full_module_path = module_name  # Top-level module
                    else:
                        full_module_path = f"{module_relative_path.replace(os.sep, '.')}.{module_name}"

                    module_list.append(full_module_path)
        return module_list

    def load_class(self, module_name, class_name, *args, **kwargs):
        """Dynamically loads a class from a module and returns an instance with provided arguments."""
        modules = self.discover_modules()
        if module_name not in modules:
            current_app.logger.debug(modules)
            current_app.logger.error(f"Module {module_name}:{class_name} not found.")
            return None
        else:
            current_app.logger.debug(f"Module {module_name}:{class_name} was found.")
            
        
        try:
            path = f"{self.module_path.replace('/', '.')}.{module_name}"
            print(f'Loading module:{path}')
            #module = importlib.import_module(path)
            
            #print(os.getcwd())
            #print(os.listdir('.'))
            
            sys.path.append("..")
            #print(sys.path)
            module = importlib.import_module(path)
            
            
            print(f'Getting class:{class_name}')
            class_ = getattr(module, class_name)  # Get the class dynamically
            print(f'Class created')
            return class_()  # Instantiate the class with arguments
            
        
        except ModuleNotFoundError as e:
            current_app.logger.error(f"Module not found: '{module_name}': {e}")
            return None
        except AttributeError as e:
            current_app.logger.error(f"Class '{class_name}' not found in module '{module_name}': {e}")
            return None
        except TypeError as e:
            current_app.logger.error(f"Type error when loading class '{class_name}' from '{module_name}': {e}")
            return None
        
        

    def load_and_run(self, module_name, class_name, *args, **kwargs):
        """Loads a module, runs its class method, then unloads it."""
        
        current_app.logger.info(f'Attempting to load class:{class_name}')
        
        module_name = module_name.replace("/", ".") 
        
        instance = self.load_class(module_name, class_name, *args, **kwargs)
        #instance = OperateGame()
        
        
        if not instance:
            error = f"Class '{class_name}' in '{module_name}' could not be loaded."
            return {'success':False,'error':error,'status':500}
        
        current_app.logger.info(f'Class Loaded:{class_name}')
        
        if hasattr(instance, "run"):
            payload = kwargs.get('payload')  # Extract payload from kwargs
            result = instance.run(payload)  # Pass payload to run
        else:
            error = f"Class '{class_name}' in '{module_name}' has no 'run' method."
            current_app.logger.error(error)
            return {'success':False,'error':error,'status':500}

        # Unload module to free memory
        del instance
        if module_name in sys.modules:
            del sys.modules[module_name]
        gc.collect()
        
        if 'success' in result and not result['success']:
            return {'success':False,'output':result,'status':400}
            
        
        return {'success':True,'output':result,'status':200}

# Example Usage
if __name__ == "__main__":
    SHL = SchdLoader()

    current_app.logger.error("Available Modules:", SHL.modules)

    # Example data to pass to classes
    data = {"message": "Hello from main.py!"}

    # Load and run `CreatePost` from `social.create_post`
    SHL.load_and_run("social.create_post", "CreatePost", data)

    # Load and run `CheckForWinners` from `gartic.check_for_winners`
    SHL.load_and_run("gartic.check_for_winners", "CheckForWinners", "Winner Data")