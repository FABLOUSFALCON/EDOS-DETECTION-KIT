import csv
from typing import Protocol

import requests

from .utils import get_logger


class OutputWriter(Protocol):
    def write(self, data: dict) -> None:
        raise NotImplementedError


class CSVWriter(OutputWriter):
    def __init__(self, output_file) -> None:
        self.file = open(output_file, "w")
        self.line = 0
        self.writer = csv.writer(self.file)

    def write(self, data: dict) -> None:
        if self.line == 0:
            self.writer.writerow(data.keys())

        self.writer.writerow(data.values())
        self.file.flush()
        self.line += 1

    def __del__(self):
        self.file.close()


class HttpWriter(OutputWriter):
    def __init__(self, output_url) -> None:
        self.url = output_url
        self.session = requests.Session()
        self.logger = get_logger(False)  # Add logger

    def write(self, data):
        try:
            # Updated to use your client and resource IDs
            enhanced_data = {
                "client_id": "cicflow-monitor-01",  # Your client ID
                "resource_id": "res_001",  # Your resource ID (Production Server)
                **data,  # Merge original flow data
            }
            resp = self.session.post(self.url, json=enhanced_data, timeout=5)
            resp.raise_for_status()  # raise if not 2xx
        except Exception:
            self.logger.exception("HTTPWriter failed posting flow")

    def __del__(self):
        self.session.close()


def output_writer_factory(output_mode, output) -> OutputWriter:
    if output_mode == "url":
        return HttpWriter(output)
    elif output_mode == "csv":
        return CSVWriter(output)
    else:
        raise RuntimeError("no output_mode provided")
