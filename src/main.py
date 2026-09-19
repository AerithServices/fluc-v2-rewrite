import sys
import dotenv
import logging
import utils
from utils.state import State
from app_types.config import UtilsConfig, BotConfig, VerifyConfig

log = logging.getLogger('root')

def main():
    if len(sys.argv) == 1:
        print("You have not chosen a bot to run!")
        print(f"Usage: python3 {sys.argv[0]} nuke/raid/utility/website/api")
        sys.exit(1)

    bot = ' '.join(sys.argv[1:])

    # Cache verify config
    with open('config/verify.json') as file:
        verify_config = VerifyConfig.model_validate_json(file.read())
    State.verify_config = verify_config

    # Setup logging
    with open('config/utils.json') as file:
        # Load and test config
        utils_config: UtilsConfig = UtilsConfig.model_validate_json(file.read())

    options: dict = {
        'level': logging.INFO
    }

    if utils_config.logging:
        options['level'] = utils_config.logging.log_level
        if utils_config.logging.file_logging:
            file_logging = utils_config.logging.file_logging
            if file_logging.log_level and file_logging.file_name:
                options.update({
                    'file_name': file_logging.file_name,
                    'file_level': file_logging.log_level
                })
        if utils_config.logging.format:
            format_config = utils_config.logging.format
            levels = format_config.levels
            options.update({
                'levels': levels and levels.model_dump() or None,
                'time_fmt': format_config.time_fmt,
                'center_level': format_config.center_level
            })

    with open('config/bot.json') as file:
        bot_config = BotConfig.model_validate_json(file.read())

    # Security settings
    State.protected_servers = bot_config.protected_servers
    State.owner_ids = bot_config.owner_ids
    State.command_prefixes = bot_config.command_prefix
    if bot_config.premium and bot_config.premium.cooldown_coefficient:
        State.cooldown_coefficient = bot_config.premium.cooldown_coefficient
    else:
        State.cooldown_coefficient = 1

    # Clean up
    del utils_config
    del bot_config

    utils.setup_logging(**options)
    # Load environment variables and run
    if dotenv.load_dotenv():
        try:
            # Check if bot exists, also runs __init__.py
            # This way we save memory by not  importing bots we don't use
            __import__(f'apps.{bot}', fromlist=['app']) # Runner
        except ModuleNotFoundError as exc:
            if exc.name != bot:
                raise
            # Bot does not exist
            log.error("Bot does not exist.")
        except KeyboardInterrupt:
            log.info('Bot closed.')
    else:
        log.error("Failed to load environment file.")
    log.info("Shutdown.")
    
if __name__ == "__main__":
    main()
else:
    log.error("Please do not import this file, it is not a module.")
    sys.exit(1)
