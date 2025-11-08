import re
from datetime import datetime


class ChatParser:
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.datetime_format = "%d/%m/%Y, %H:%M"
        self.dateTimeRegex = "^\d{2}/\d{2}/\d{4}\,\s+\d{2}:\d{2}"
        self.nameRegex = "^[^:]+"
        
        self.nonStandardRows = []

        self.raw_data = self.load_data()
        self._chat = self.raw_data
        self.parsed_data = self.parse_data()
        

    def load_data(self):
        with open(self.filepath, "r") as file:
            return [line for i, line in enumerate(file) if i > 0]

    def extract_datetimes(self):
        messageDateTimes = []
        for row, message in enumerate(self._chat):
            messageDateTime = re.findall(self.dateTimeRegex, message)
            messageDateTime = (
                datetime.strptime(messageDateTime[0], self.datetime_format)
                if len(messageDateTime) > 0
                else None
            )
            self.nonStandardRows.append(row) if messageDateTime is None else None
            messageDateTimes.append(messageDateTime)

        for i, message in enumerate(self._chat):
            message = re.sub(self.dateTimeRegex, "", message)
            message = re.sub(" - ", "", message)
            self._chat[i] = message
        return messageDateTimes

    def extract_names(self):
        messageNames = []
        for row, message in enumerate(self._chat):
            if row not in self.nonStandardRows:
                messageNames.append(re.findall(self.nameRegex, message)[0])

            else:
                messageNames.append(None)

        for i, message in enumerate(self._chat):
            message = re.sub(self.nameRegex + ": ", "", message)
            self._chat[i] = message.strip()

        return messageNames

    def parse_data(self):
        dateTimes = self.extract_datetimes()
        names = self.extract_names()

        return {
            row: {"date": dateTimes[row], "author": names[row], "text": self._chat[row]}
            for row in range(0, len(self._chat))
        }
    
    def merge_messages(self):
        """Method to merge together messages from the same author. Seperate messages are concatenated with an <eom> (end of message) marker"""
        endOfNewAuthors = None
        combinedReplyI = 0
        combinedMessages = {}

        for key, value in self.parsed_data.items():
            if (endOfNewAuthors is None) or (key > endOfNewAuthors):
                if key < len(self.parsed_data) - 1:
                    # work out how many more message consequetive messages are by the same author
                    consequetiveAuthors = []
                    for i in range(key, len(self.parsed_data)):
                        if self.parsed_data[i]["author"] == value["author"]:
                            consequetiveAuthors.append(i)
                        else:
                            break
                    endOfNewAuthors = (
                        max(consequetiveAuthors) if len(consequetiveAuthors) > 0 else i
                    )

                    combined_text = " <eom> ".join(
                        [self.parsed_data[i]["text"] for i in range(key, endOfNewAuthors + 1)]
                    ) + " <eom>"
                    combinedMessages[combinedReplyI] = {value["author"]: combined_text}
                    combinedReplyI = combinedReplyI + 1
        
        return combinedMessages