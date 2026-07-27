ACORN_RELEASE = "v0.1.0"
WELCOME_MSG = """THIS SOFTWARE IS USED WITHOUT WARRANTY OR LIABILITY TO ITS AUTHOR.
"""
INFO_HELP = f"""This is the help for the acorn info command.

Acorn release is: {ACORN_RELEASE}.

The info function displays general information and confirms that the command line interface is working properly."""

SET_HELP = f"""This is the help for the acorn set command.

The set function sets local configuration options. All configuration information is stored UNENCRYPTED in your home directory of ~/.acorn/config.yml.
"""

NSEC_HELP= """
This option to set to an existing nsec. Be sure you know what you are doing when using this option, and never set it to your personal nsec.
"""

RELAYS_HELP= """
Relays that are used to read posts and profiles. 
"""
HOME_RELAY_HELP= """
The home relay is where Acorn wallet and record events are published to and retrieved from. Be sure to use a relay that you trust for availability. Relay operators cannot see your encrypted data but may decide to block your access. Be ready to replicate your data should your home relay become unreliable or adversarial.
"""

MINTS_HELP ="""
The mints that are used by Acorn. The first mint specified in the list is the home mint.
"""

NOSTR_PROFILE_HELP ="""
Each wallet can have its own nostr profile published.
"""
