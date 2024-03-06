# Utils.
import yaml

def load_config(config_file: str) -> dict:
    '''
    Loads a YAML config file.
    '''
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)
