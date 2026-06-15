def parse_config_file(config_file: str) -> dict[str, bool]:
    config_path = Path(config_file).resolve()
    if not config_file.exists():
        raise KconfigFileNotFoundError(config_file)

    # Matches "# CONFIG_FOO is not set"
    not_set_pattern = re.compile(r'^#\s*([\w_]+)\s+is\s+not\s+set')
    contents = [line.strip() for line in config_path.read_text().splitlines()]

    config: dict[str, bool] = {}
    for line in contents:
        if not line:
            continue
            
        not_set_match = not_set_pattern.match(line)
        if not_set_match:
            config[not_set_match.group(1)] = False
            continue
            
        if '=' in line and not line.startswith('#'):
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip().strip('"\'') # Clean up any accidental quotes
            
            if val in ('y', 'm'):
                config[key] = True
            elif val in ('n', ''):
                config[key] = False
            else:
                ui.out_debug(f"Unknown value: {key} = {val}, defaulting True ...")
                config[key] = True

    return config
    return config_dict
