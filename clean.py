# Cleaning the text.
import argparse
import json
import os
import re

from typing import Optional

import ftfy

from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

from utils import load_config

# Seeds, configs and patterns.
# RegEx patterns
EXCESSIVE_CHARS_PATTERN = re.compile(r"(\.|\-|\*|!)\1{3,}")
EXTRA_NEWLINE_PATTERN = re.compile(r"\n{3,}")
MARKDOWN_IMAGE_EMBED_PATTERN = re.compile(r"!\[.*?\]\(.*?\)\n*")
UNSPACED_PUNCTUATION_PATTERN = re.compile(r"([a-z]{2,})(\.|!|\?)([A-Z])")
WEIRD_DASH_PATTERN = re.compile(r"^\s?[—-]+\s*", flags=re.MULTILINE)
# ftfy config
ftfy_config = ftfy.TextFixerConfig(
    fix_latin_ligatures=False,
    fix_character_width=False,
    # We don't need explanations and extra speed is wanted.
    explain=False
)
# langdetect seed
DetectorFactory.seed = 0
# Files.
THIS_DIR = os.path.realpath(os.path.dirname(__file__))

def main(config_file: str) -> None:
    '''
    Cleans conversations (right now supports only PIPPA)
    '''
    # Load the config file. Only the cleaning section is needed.
    #config_path = os.path.join(THIS_DIR, 'data', config_file)
    config = load_config(config_file)['cleaning']
    new_file_name = os.path.basename(config['pippa_file']).split('.')[0] + '_cleaned.jsonl'
    new_path = os.path.join(THIS_DIR, 'data', new_file_name)
    old_path = os.path.join(THIS_DIR, 'data', config['pippa_file'])

    # Load the text.
    with open(old_path, 'r', encoding="utf-8") as rf, open(new_path, 'w', encoding="utf-8") as wf:
        for line in rf:
            entry = json.loads(line)
            conversation = entry['conversation']
            char_name = entry['bot_name']
            cleaned_conversation = clean_conversation(conversation, char_name, config['language_threshold'])
            entry['conversation'] = cleaned_conversation
            if cleaned_conversation:
                wf.write(json.dumps(entry) + '\n')
            else:
                print(f"Conversation is not in English: {conversation}")

    print("Done!")

# Utility function.
        
def clean_conversation(conversation: list[dict], char_name: str, threshold: float) -> Optional[list[dict]]:
    '''
    Cleans a conversation.
    Args:
    conversation (list[dict]): The conversation to clean.
    threshold: The ratio of non-English messages to total messages that when passed, discards a conversation
    '''
    # If the conversation is not in English, discard it.
    if not _is_english(conversation, threshold):
        return None

    # Clean each message.
    for turn in conversation:
        turn['message'] = _clean_text(turn['message'])

    # Deal with redactions and {{char}}
    conversation = sub_names(conversation, char_name)

    return conversation

def sub_names(conversation: list[dict], char_name: str) -> str:
    '''
    Replaces redacted names with "{{user}}" (will be changed later during augmentation) and {{char}} with the character's name.
    '''
    for m in conversation:
        msg = m['message']
        msg = msg.replace("{{char}}", char_name)
        for redaction_token in [
                "[NAME_IN_MESSAGE_REDACTED]",
                "[REDACTED]",
                "[FIRST_NAME_REDACTED]",
                "[USERNAME_REDACTED]",
                "[NAME_REDACTED]",
        ]:
            msg = msg.replace(redaction_token, "{{user}}")
        m['message'] = msg

    return conversation
        
def _clean_text(text: str) -> str:
    '''
    Cleans a text.
    '''
    # Strip the text.
    message = text.strip()

    message = EXTRA_NEWLINE_PATTERN.sub("\n\n", message)
    message = MARKDOWN_IMAGE_EMBED_PATTERN.sub("", message)

    message = re.sub(r"(\S)(…|\.\.\.)(\S)", "\\1\\2 \\3", message)
    message = EXCESSIVE_CHARS_PATTERN.sub(r"\1\1\1", message)

    message = message.replace(" .. ", "... ")
    message = message.replace(" ... ", "... ")
    message = re.sub(r'\b(\.\.\.?)\b', '... ', message)

    message = message.replace(" . ", ". ")
    message = message.replace(" , ", ", ")
    message = message.replace(" ? ", "? ")
    message = message.replace(" ! ", "! ")

    message = UNSPACED_PUNCTUATION_PATTERN.sub(r"\1\2 \3", message)

    # Fix hidden zero-width spaces and other whitespace fuckery which could
    # mess with a model.
    message = message.replace(" ", "")
    message = message.replace("​", "")
    message = message.replace("‍", " ")
    message = message.replace(" ", " ")
    message = message.replace("﻿", " ")
    message = message.replace("", "")
    message = message.replace("‎", "")

    # Use ftfy to fix any encoding issues.
    message = ftfy.fix_text(message, config=ftfy_config)

    message = message.replace("  ", " ")
    # Deal with odd escape sequences.
    message = message.replace("\\n", "\n")
    message = message.replace("\\~", "~")
    message = message.replace("\\-", "-")
    # And spaces before newlines...
    message = re.sub(r" *\n", "\n", message)
    # And other Unicode.
    message = message.replace("…", "...")
    message = WEIRD_DASH_PATTERN.sub("", message)
    message = message.replace("—", "-")

    return message

def _is_english(conversation: list[dict], threshold: float) -> bool:
    '''
    Detects the language of a conversation to see if it's English.
    If it is, returns True. Otherwise, returns False.
    Args:
    conversation (list[dict]): The conversation to scan languages for.
    threshold: The ratio of non-English messages to total messages that when passed, discards a conversation
    '''
    num_not_english = 0
    for turn in conversation:
        try:
            if detect(turn['message']) != "en":
                num_not_english += 1
        except LangDetectException:
            # If langdetect throws an error, assume it's not English.
            num_not_english += 1

    if num_not_english / len(conversation) > threshold:
        return False
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleans conversations")
    parser.add_argument("-c", "--config", type=str, required=True, help="The config file to use")
    args = parser.parse_args()

    main(args.config)
