import urllib.request
import subprocess
import os
import tempfile
import shutil
import json
import re
from bs4 import BeautifulSoup
from dzclient import DatazillaRequest, DatazillaResult

try:
    import ConfigParser
except:
    from winpython.py3compat import configparser as ConfigParser

def edit_config_file(config_file, url):
    try:
        with open(config_file, 'r') as f:
            pconfig = json.load(f)

        with open(config_file, 'w') as f:
            iter = 0
            for product in pconfig["OS"]["Windows"]:
                if product["name"] == "Firefox":
                    pconfig["OS"]["Windows"][iter]["url"] = url
                iter = iter + 1
            json.dump(pconfig, f)
            return True
    except IOError:
        print("Error writing file: %s" % config_file)
        return False

def check_build(build):
    """Check the build url to see if build is available. build can
    be either a direct link to a build or a link to a directory
    containing the build. If the build is available, then
    check_build will return the actual url to the build.
    """
    buildurl = None
    re_builds = re.compile(r"firefox-([0-9]+).*\.win32\.installer\.exe")

    if not build.endswith("/"):
        # direct url to a build implies the build is available now.
        buildurl = build
    else:
        try:
            builddir_content = urllib.request.urlopen(build).read()
            builddir_soup = BeautifulSoup(builddir_content)
            for build_link in builddir_soup.findAll("a"):
                match = re_builds.match(build_link.get("href"))
                if match:
                    buildurl = "%s%s" % (build, build_link.get("href"))
        except:
            # Which exceptions here? from urllib, BeautifulSoup
            print("Error checking build")
            buildurl = None

    if buildurl:
        try:
            builddir_content = urllib.request.urlopen(build).read()
        except:
            buildurl = None

    return buildurl

def download_build(url, configinfo):
    # Download a build and extra build information.
    try:
        if os.path.exists(configinfo['firefox_path']):
            os.unlink(configinfo['firefox_path'])

        builddir_content = urllib.request.urlopen(url).read()
        with open(configinfo['firefox_path'], 'wb') as f:
            f.write(builddir_content)

    except IOError:
        print("Error downloading build")
        return False

    if not edit_config_file(CONFIG_FILE, url):
        print("error editing config file")
        return False

    # Get information about the build by extracting the installer
    # to a temporary directory and parsing the application.ini file.
    tempdirectory = tempfile.mkdtemp()
    returncode = subprocess.call(["7z", "x", configinfo['firefox_path'],
                                  "-o%s" % tempdirectory])

    appinfo = {}
    appini = ConfigParser.RawConfigParser()
    appini.readfp(open("%s/core/application.ini" % tempdirectory))
    appinfo['build_name'] = appini.get("App", "name")
    appinfo['build_version'] = appini.get("App", "version")
    appinfo['build_id'] = appini.get("App", "buildID")
    appinfo['build_branch'] = os.path.basename(appini.get("App", "SourceRepository"))
    appinfo['build_revision'] = appini.get("App", "SourceStamp")
    appinfo['url'] = url

    if returncode != 0:
        raise Exception("download_build: "
                        "error extracting build: rc=%d" % returncode)
    shutil.rmtree(tempdirectory)

    return appinfo


def run_benchmark(appinfo, configinfo):
    """Submit jobs for this location for each speed and url.
    """
    #TODO: we need to queue these up somehow- launch one at a time and make this serial
    ed = configinfo['energia_dir']
    cmd = ['python3', os.path.join(ed, 'benchmark.py'), '-o', os.path.join(ed, 'report.csv')]
    p = subprocess.Popen(cmd, cwd=ed, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(p.communicate()[0])

def post_to_datazilla(appinfo, configinfo):
    """ take test_results (json) and upload them to datazilla """

    with open(os.path.join(configinfo['energia_dir'], '/report.csv'), 'r') as fHandle:
        data = fHandle.readlines()

    header = True
    browsers = []
    for line in data:
        if header:
            header = False
            continue
        parts = line.split(',')
        if parts[1] not in browsers:
            browsers.append(parts[1])

    for browser in browsers:
        result = DatazillaResult()
        suite_name = "PowerGadget"
        machine_name = "tor-win8"
        os_name = "Win"
        browsername = browser
        if browsername == "Internet Explorer":
            browsrename = "IE"
        os_version = "8 - %s" % browsername
        platform = "x64"
    
        result.add_testsuite(suite_name)
        request = DatazillaRequest("https",
                               "datazilla.mozilla.org",
                               "power",
                               configinfo['oauth_key'],
                               configinfo['oauth_secret'],
                               machine_name=machine_name,
                               os=os_name,
                               os_version=os_version,
                               platform=platform,
                               build_name=appinfo['build_name'],
                               version=appinfo['build_version'],
                               revision=appinfo['build_revision'],
                               branch=appinfo['build_branch'],
                               id=appinfo['build_id'])

        header = True
        for line in data:
            if header:
                header = False
                continue
            parts = line.split(',')

            #Skip data from other browsers
            if parts[1] != browser:
                continue

            result.add_test_results(suite_name, parts[13], [str(parts[14])])
            print("JMAHER: added data: %s: %s = %s, %s" % (os_version, suite_name, parts[13], [str(parts[14])]))

        request.add_datazilla_result(result)
        responses = request.submit()
        for resp in responses:
            print('server response: %d %s %s' % (resp.status, resp.reason, resp.read()))

def main():
    configinfo = {}

    configini = ConfigParser.RawConfigParser()
    configini.readfp(open("%s/core/application.ini" % tempdirectory))

    configinfo['energia_dir'] = configini.get("Energia", "dir")
    configinfo['config_file'] = configini.get("Energia", "config")
    configinfo['firefox_path'] = configini.get("Energia", "firefox")
    configinfo['oauth_key'] = configini.get("Energia", "oauth_key")
    configinfo['oauth_secret'] = configini.get("Energia", "oauth_secret")
    configinfo['ftp_root'] = configini.get("Energia", "ftp")

    buildurl = check_build(configinfo['ftp_root'])
    appinfo = download_build(buildurl, configinfo)
    run_benchmark(appinfo, configinfo)
    post_to_datazilla(appinfo, configinfo)

if __name__ == "__main__":
    main()


