"""Task Logging Module for Makimm."""

import datetime

from enum import Enum
from typing import Any, TextIO


class LogLevel(Enum):
    """Enum of log levels."""

    ERR = 'err'
    OUT = 'out'
    BOTH = 'both'


class Tee:
    """A stream wrapper that writes data to multiple streams simultaneously."""

    def __init__(self, *streams: TextIO) -> None:
        """
        Initialize the Tee stream with output streams.

        Parameters
        ----------
        streams : TextIO
            Streams where data will be appended.
        """
        self.streams: tuple[TextIO, ...] = streams

    def write(self, data: Any) -> None:
        """
        Write data to all given streams.

        Parameters
        ----------
        data : str or bytes
            The data to be written.
        """
        # Convert data bytes to utf-8
        if isinstance(data, bytes):
            data = data.decode('utf-8', errors='replace')

        for stream in self.streams:
            stream.write(data)

    def flush(self) -> None:
        """Flush all given streams."""
        for stream in self.streams:
            stream.flush()


class FormattedLogStream:
    """A stream wrapper that formats log messages based on format string."""

    def __init__(
        self,
        stream: TextIO,
        format: str,
        level: LogLevel,
        task: str,
        file: str,
    ) -> None:
        """
        Initialize the FormattedLogStream.

        Parameters
        ----------
        stream : TextIO
            The file stream to append logs.
        format : str
            The log format string (example, %(asctime)s - %(message)s").
        level : LogLevel
            The log level as specified in the task configuration.
        task : str
            The task from where logs are streamed.
        file : str
            The file where task is defined.
        """
        self.stream = stream
        self.format = format
        self.level = level.value.upper()
        self.task = task
        self.file = file
        self._buffer = ''

    def write(self, data: Any) -> None:
        """
        Write formatted log records.

        Parameters
        ----------
        data : str or bytes
            The data to write.
        """
        # Convert data bytes to utf-8
        if isinstance(data, bytes):
            data = data.decode('utf-8', errors='replace')
        self._buffer += data
        while '\n' in self._buffer:
            text, self._buffer = self._buffer.split('\n', 1)
            record = {
                'asctime': datetime.datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S'
                ),
                'task': self.task,
                'file': self.file,
                'levelname': self.level,
                'message': text,
            }
            formatted_line = self.format % record
            self.stream.write(formatted_line + '\n')

    def flush(self) -> None:
        """Send any pending text to the given stream."""
        if not self._buffer:
            self.stream.flush()
            return

        record = {
            'asctime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'task': self.task,
            'file': self.file,
            'levelname': self.level,
            'message': self._buffer,
        }
        formatted_line = self.format % record
        self.stream.write(formatted_line + '\n')
        self._buffer = ''
