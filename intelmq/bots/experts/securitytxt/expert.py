from typing import Optional

import requests
from securitytxt import SecurityTXT

from intelmq.lib.bot import ExpertBot


class SecurityTXTExpertBot(ExpertBot):
    """
    A bot for retrieving contact details from a security.txt
    """
    """
    url_field: The field where to find the url which should be searched
    contact_field: Field in which to place the found contact details

    only_email_address: whether to select only email addresses as contact detail (no web urls)
    overwrite: whether to override existing data
    check_expired / check_canonical: whether to perform checks on expiry date / canonical urls.
    """
    url_field: str = "source.reverse_dns"
    contact_field: str = "source.abuse_contact"

    only_email_address: bool = True
    overwrite: bool = True
    check_expired: bool = False
    check_canonical: bool = False

    def init(self):
        if not self.url_field or not self.contact_field:
            raise AttributeError("Not all required fields are set.")

    def process(self):
        event = self.receive_message()

        try:
            self.check_prerequisites(event)
            primary_contact = self.get_primary_contact(event.get(self.url_field))
            event.add(self.contact_field, primary_contact, overwrite=self.overwrite)
        except NotMeetsRequirementsError as e:
            self.logger.debug(str(e) + " Skipping event.")
        except ContactNotFoundError as e:
            self.logger.debug(f"No contact found. {str(e)} Continue.")

        self.send_message(event)
        self.acknowledge_message()

    def check_prerequisites(self, event) -> None:
        """
        Check whether this event should be processed by this bot, or can be skipped.
        :param event: The event to evaluate.
        """
        if not event.get(self.url_field, False):
            raise NotMeetsRequirementsError("The URL field is empty.")
        if event.get(self.contact_field, False) and not self.overwrite:
            raise NotMeetsRequirementsError("All replace values already set.")

    def get_primary_contact(self, url: str) -> Optional[str]:
        """
        Given a url, get the file, check it's validity and look for contact details. The primary contact details are
        returned. If only_email_address is set to True, it will only return email addresses (no urls).
        :param url: The URL on which to look for a security.txt file
        :return: The contact information
        :raises ContactNotFoundError: if contact cannot be found
        """
        try:
            securitytxt = SecurityTXT.from_url(url)
            if not self.security_txt_is_valid(securitytxt):
                raise ContactNotFoundError("SecurityTXT File not valid.")
            for contact in securitytxt.contact:
                if not self.only_email_address or SecurityTXTExpertBot.is_email_address(contact):
                    return contact
            raise ContactNotFoundError("No contact details found in SecurityTXT.")
        except (FileNotFoundError, AttributeError, requests.exceptions.RequestException):
            raise ContactNotFoundError("SecurityTXT file could not be found or parsed.")

    def security_txt_is_valid(self, securitytxt: SecurityTXT):
        """
        Determine whether a security.txt file is valid according to parameters of the bot.
        :param securitytxt: The securityTXT object
        :return: Whether the securitytxt is valid.
        """
        return (not self.check_expired or not securitytxt.expired) and \
               (not self.check_canonical or securitytxt.canonical_url())

    @staticmethod
    def is_email_address(contact: str):
        """
        Determine whether the argument is an email address
        :param contact: the contact
        :return: whether contact is email address
        """
        return 'mailto:' in contact or '@' in contact


class NotMeetsRequirementsError(Exception):
    pass


class ContactNotFoundError(Exception):
    pass


BOT = SecurityTXTExpertBot