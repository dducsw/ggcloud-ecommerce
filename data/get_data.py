import os
import shutil
import kagglehub

def download_data():
    # Current directory of get_data.py (the 'data' folder)
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("Downloading data from Kaggle...")
    # Download dataset to local cache
    cache_path = kagglehub.dataset_download("daichiuchigashima/thelook-ecommerce")
    
    print(f"Data downloaded to cache at: {cache_path}")
    print(f"Copying data to: {output_dir}")
    
    # Copy files from cache to the data directory
    for filename in os.listdir(cache_path):
        source = os.path.join(cache_path, filename)
        destination = os.path.join(output_dir, filename)
        
        if os.path.isfile(source):
            shutil.copy2(source, destination)
            print(f"Saved: {filename}")

    print("Data download complete!")

if __name__ == "__main__":
    download_data()