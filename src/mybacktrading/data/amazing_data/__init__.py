import os
from typing import List

save_dir = os.path.join(os.getcwd(), "csv_data")
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

def download_data(symbols: List[str]):
    pass
