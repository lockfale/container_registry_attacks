import os
import subprocess
import requests
import base64
import json
from argparse import ArgumentParser

#Credit: https://digital-shokunin.net

def get_args():
  parser = ArgumentParser()
  parser.add_argument('-r','--registry', default='gchr.io', help='Ex: ghcr.io')
  parser.add_argument('-o','--outputdir', default=f"{os.getcwd()}/output", help='Output directory, default: <current_working_directory>/output')
  return parser.parse_args()

def get_docker_registry_catalog(registry_url):
  catalog_url = f"{registry_url}/v2/_catalog"
  response = requests.get(catalog_url)
  if response.status_code == 200:
    return response.json()["respositories"]
  else: 
    print(f"Error getting catalog: {response.status_code}")
    return []

def get_image_tags(registry_url, image_name):
  tags_url = f"{registry_url}/v2/{image_name}/tags/list"
  response = requests.get(tags_url)
  if response.status_code == 200:
    return response.json()["tags"]
  else:
    print(f"Error getting tags for {image_name}: {response.status_code}")
    return []

def get_auth_string(config_file, registry):
  with open(config_file, 'r') as file:
    config_data = json.load(file)
  auths = config_data.get("auths")
  if auths:
    registry_data = auths.get(f"https://{registry}")
    if registry_data:
      auth_string = registry_data.get("auth")
      if auth_string:
        return auth_string
      else:
        print(f"No auth data found for registry '{registry}' in Docker config.json")
    else:
      print(f"No data found for registry '{registry}' in Docker config.json")
  else:
    print(f"No auth entries found in Docker config.json file")
  return None

def check_directory(directory):
  if not os.path.exists(directory):
    os.makedirs(directory)

def run_command(command):
  process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
  stdout, stderr = process.communicate()
  return_code = process.returncode
  if return_code == 0:
    return stdout.decode('utf-8')
  else:
    print(f"Error executing command: {stderr.decode('utf-8')}")
    return None
  
def docker_pull(docker_image):
  result = run_command(f"docker pull {docker_image}")
  if result:
    print(f"Docker image pulled: {docker_image}")

def docker_rmi(docker_image):
  result = run_command(f"docker rmi {docker_image}")
  if result:
    print(f"Docker image removed: {docker_image}")

def run_scans(registry, image_name, tag, output_dir, docker_image=None):
  """
    Run Docker scans

    Parameters:
        registry (string): Registry for image to be scanned
        image_name (string): Name of Docker image to be scanned
        tag (string): Tag for the Docker image to be scanned
        output_dir (string): Output directory for scan output
        docker_image (string): Optional, full Docker image string
  """
  if docker_image is None:
    docker_image=f"{registry}/{image_name}:{tag}"

  if not len(image_name.split('/')[0]) == 0:
    check_directory(f"{output_dir}/{registry}/{image_name.split('/')[0]}")
  else:
    check_directory(f"{output_dir}/{registry}")

  vuln_report = f"{output_dir}/{registry}/{image_name}_{tag}_vulnerabilities.json"
  secrets_report = f"{output_dir}/{registry}/{image_name}_{tag}_secrets.json"

  if not os.path.isfile(vuln_report) and not os.path.isfile(secrets_report): #Skip if scan has been done report and only run secret report if already done
    docker_pull(docker_image)
    print(f"Scanning {docker_image}")
    scan1 = f"trivy image {docker_image} --scanners vuln,config --report all --timeout 5m --format json > {vuln_report}"
    result = run_command(scan1)
    if result:
      print(result)
    if not os.path.isfile(secrets_report):
      scan2 = f"trivy image {docker_image} --scanners secret --report all --timeout 5m --format json > {secrets_report}"
      result = run_command(scan2)
      if result:
        print(result)
    docker_rmi(docker_image)
  else:
    print(f"{docker_image} already scanned, skipping...")

def main(registry, output_dir):
  home = os.path.expanduser("~")
  docker_config_file=f"{home}/.docker/config.json"
  auth_string = get_auth_string(docker_config_file, registry)

  registry_url = f"https://{base64.b64decode(auth_string).decode('utf-8')}@{registry}"
  image_names = get_docker_registry_catalog(registry_url)
  num_images = len(image_names)
  images_scanned = 0
  for image_name in image_names:
    tags = get_image_tags(registry_url, image_name)
    images_scanned += 1
    num_tags = len(tags)
    total_images = num_images * num_tags
    tags_scanned = 0
    for tag in tags:
      tags_scanned += 1
      run_scans(registry, image_name, tag, output_dir)
      print(f"Scanned {images_scanned} of {num_images}, Tag {tags_scanned} of {num_tags}")
      print(f"{total_images - (images_scanned * tags_scanned)} left")


if __name__ == "__main__":
  args = get_args()
  main(args.registry, args.outputdir)
