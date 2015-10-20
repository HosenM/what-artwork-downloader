'''
Created on 14.02.2015

'''

import os
import logging
import urllib.request
import shutil
import sys
import configparser
import pickle
import re

DEBUG = False

logger = logging.getLogger('artwork_downloader')
ch = logging.StreamHandler()
if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s - %(message)s')
ch.setFormatter(formatter)

logger.addHandler(ch)
logger.info('Hello')

def install_package(package):
    import pip
    try:
        pip.main(['install', '--upgrade', package])
    except Exception as e:
        sys.exit("Couldn't install {} with pip - {}".format(package, e))
    

try:
    import requests
except ImportError:
    logger.warning("Requests is not installed - will try to install it now via pip")
    install_package("requests")
    try:
        import requests
    except ImportError as e:
        sys.exit("Failed to install requests - {}".format(e))

try:
    from PIL import Image
except ImportError:
    logger.warning("Pillow is not installed - will try to install it now via pip")
    install_package("Pillow")
    try:
        from PIL import Image
    except ImportError as e:
        sys.exit("Failed to install Pillow - {}".format(e))

try:
    import whatapi
except ImportError:
    logger.warning("WhatAPI is not installed - will try to install it now via pip")
    install_package("https://github.com/capital-G/whatapi/tarball/master")
    try:
        import whatapi
    except ImportError as e:
        sys.exit("Failed to install WhatAPI - {}".format(e))

try:
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.easyid3 import EasyID3 as MP3
except ImportError:
    logger.warning("mutagen is not installed - will try to install it now via pip")
    install_package("mutagen")
    try:
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
        from mutagen.easyid3 import EasyID3 as MP3
    except ImportError as e:
        sys.exit("Failed to install mutagen - {}".format(e))


class ArtworkFinder():
    def __init__(self, **kwargs):
        self._config = kwargs.get('config')
        self._whatcd_api = kwargs.get('whatcdapi')
        self._artist = kwargs.get('artist', None)
        self._album = kwargs.get('album', None)
        self._entity = kwargs.get('entity', 'album')
        if self._config['iTunes'].getboolean('use'):
            countries_string = self._config['iTunes']['countries']
            self._countries = countries_string.split(',')
        self._path = os.path.dirname(kwargs.get('file'))
        self._source = None
        
        delete_chars = ("various", "artists", "{", "}", "[", "]", "the ", ",", "(", ")",
                        "(", ")", "CD", "Deluxe", "Edition", "Remaster", "Remastered", "SACD", "MP3", "FLAC", "!", "#",
                        "disk", "disq", "disc", "bonus", "dvd")
        for char in delete_chars:
            self._artist = self._artist.lower().replace(char.lower(), " ")
        
        if "various artists" in self._path.lower():
            self._artist = ""
        
        self._album = ''.join([i for i in self._album if not i.isdigit()])

        self._name = self._artist+" "+self._album

    def get_artwork(self):
        if self._config['iTunes'].getboolean('use'):
            itunes_api_results = self.itunes_api()
            if itunes_api_results:
                store_success = self.store()
                if store_success is False:
                    logger.info("No Artwork found in iTunes for {} - {} in {}".format(self._artist.title(),
                                                                                       self._album.title(),
                                                                                       self._path))
                    return False
                logger.info("Successfully saved the iTunes Artwork for {} - {} in the folder {}".format(self._artist,
                                                                                                         self._album,
                                                                                                         self._path))
                return True
            else:
                logger.info("No Artwork found in iTunes for {} - {} in {}".format(self._artist.title(),
                                                                            self._album.title(),
                                                                            self._path))
        
        if self._config['what-cd'].getboolean('use'):
            whatcdapi_results = self.whatcd_api()
            if whatcdapi_results:
                store_success = self.store()
                if store_success is False:
                    logger.info("No Artwork found in what.CD for {} - {} in {}".format(self._artist.title(),
                                                                                        self._album.title(),
                                                                                        self._path))
                    return False
                logger.info("Sucessfully saved the what.CD Artwork for {} - {} in the folder {}".format(self._artist,
                                                                                                         self._album,
                                                                                                         self._path))

                return True
            else:
                logger.info("No Artwork found in what.CD for {} - {} in {}".format(self._artist.title(),
                                                                                    self._album.title(),
                                                                                    self._path))

        return False
    
    def itunes_api(self):
        for country in self._countries:
            request_params = {'term': self._name,
                              'entity': self._entity,
                              'country': country}
            try:
                request = requests.get("http://ax.itunes.apple.com/WebObjects/MZStoreServices.woa/wa/wsSearch",
                                       params=request_params)
            except requests.exceptions.Timeout:
                logger.error("No connection to iTunes API - check your Internet connection")
                return False

            if request.status_code != 200:
                logger.error("Error from iTunes API - Error Code {} - {}".format(request.status_code, request.text))
                return False

            if len(request.json()['results']) == 0:
                logger.info("No search results  in iTunes {} for {}".format(country, self._name))
                return False
            else:
                logger.debug("Found iTunes results for {} in {} iTunes Store".format(self._name, country))
                break
        
        self._highres_url = request.json()['results'][0].get('artworkUrl100').replace("100x100", "1200x1200")
        self._normres_url = request.json()['results'][0].get('artworkUrl100').replace("100x100", "600x600")
        logger.info("Found iTunes Artwork for {}, - {}".format(self._name, self._highres_url))
        self._source = "iTunes"
        return True

    def whatcd_api(self):
        what_request = self._whatcd_api.request("browse",searchstr=self._name)
        if len(what_request['response']['results']) == 0:
            logger.info("No What.CD results for {} - {}".format(self._artist, self._album))
            return False
        try:
            self._highres_url = what_request['response']['results'][0]['cover']

        except KeyError:
            logger.info("Found a What-CD Release but without cover")
            return False
        
        if self._highres_url == "":
            logger.info("Found a What-CD Release but without cover")
            return False
        
        logger.info("Found what.CD Artwork for {}, - {}".format(self._name, self._highres_url))
        self._source = "whatCD"
        return True
        
    def store(self):
        logger.debug("Cover-URL: {}".format(self._highres_url))
        
        downloader = urllib.request.build_opener()
        downloader.addheaders = [('User-agent', 'Mozilla/5.0')] # avoid problems with whatIMG
        file_name = re.search(r"(.+\.jpg)", self._highres_url).group(0)
        try:
            with downloader.open(self._highres_url) as \
                    response, open(os.path.join(self._path, file_name.split("/")[-1]), "wb") as out_file:
                shutil.copyfileobj(response, out_file)
        except Exception as e:
            logger.error("Couldn't write HighRes Artwork for {} - URL is {}: {}".format(self._path,
                                                                                        self._highres_url,
                                                                                        e))
            return False

        if os.path.splitext(file_name.split("/")[-1])[1] not in (".jpg", ".jpeg"):
            logger.info("The downloaded Artwork {} is not .jpg or .jpeg, "
                        "so we will convert it to .jpg now".format(file_name.split("/")[-1]))
            im = Image.open(os.path.join(self._path, file_name.split("/")[-1])).convert('RGB')
            im.save(os.path.join(self._path, self._config['folder']['jpgname']))
            os.remove(os.path.join(self._path, file_name.split("/")[-1]))
        else:
            os.rename(os.path.join(self._path, file_name.split("/")[-1]),
                      os.path.join(self._path, self._config['folder']['jpgname']))


def main():
    os.chdir(os.path.split(os.path.abspath(__file__))[0])
    
    logger.info("Welcome to artwork.py")
    
    config = configparser.ConfigParser()
    
    if os.path.isfile('artwork.ini') is False:
        if os.path.isfile('artwork.dat') is True:
            os.remove("artwork.dat")
        logger.info("SETUP")
        while True:
            user_input = input("Do you want to use iTunes as Database? (Y/N) ")
            if user_input.lower() == "y":
                countries = input("Do you want to use anything else except only the American iTunes Store? "
                                  "If so, enter the country codes separated by comma without any spaces. "
                                  "If you only want to use the US Store, hit Enter ")
                if countries == '':
                    countries = 'us'
                config['iTunes'] = {'use': True,
                                    'countries': countries}
                break
            elif user_input.lower() == "n":
                config['iTunes'] = {'use': False}
                break
        while True:
            user_input = input("Do you want to use What.CD as Database? (Y/N)")
            if user_input.lower() == "y":
                logger.info("OK, for that we will need your What-CD login")
                whatcd_user = input("What.cd Username:")
                whatcd_pw = input("What.cd Password:")
                config['what-cd'] = {'use': True,
                                     'username': whatcd_user,
                                     'password': whatcd_pw}
                break
            if user_input.lower() == "n":
                config['what-cd'] = {'use': False}
                break
        if config['iTunes'].getboolean('use') is False and config['what-cd'].getboolean('use') is False:
            sys.exit("Sorry, you must select at least one of the two choices - Goobye")
        
        while True:
            folder_input = input("Do you want to use something else as folder.jpg? (Y/N) ")
            if folder_input.lower() == "n":
                config['folder'] = {'jpgname': 'folder.jpg'}
                break
            if folder_input.lower() == "y":
                jpg_name = input("Ok, then enter your desired name: ")
                if not "." in jpg_name:
                    jpg_name += ".jpg"
                config['folder'] = {'jpgname': jpg_name}
                break
        
        with open('artwork.ini', 'w') as configfile:
            config.write(configfile)
        logger.info("Setup successful - if you want to run this setup again, "
                     "simply delete the artwork.ini file or modify it for your needs")
        
    else:
        config.read('artwork.ini')
           
    if config['what-cd'].getboolean('use') is True and os.path.isfile("artwork.dat") is False:
        logger.info("There's no cookie for your What.cd Login - so we will have to login you")
        login_tryouts = 0
        while True:
            try:
                whatcd_api = whatapi.WhatAPI(username=config['what-cd']['username'],
                                             password=config['what-cd']['password'])
                pickle.dump(whatcd_api.session.cookies, open('artwork.dat', 'wb'))
                break

            except Exception as e:
                login_tryouts += 1
                if login_tryouts > 3:
                    logger.error("It seems What-CD is down, so we won't use that now this time")
                    config['what-cd'] = {'use':False}
                    if config['iTunes'].getboolean('use') is False:
                        sys.exit("No iTunes and what.CD search is now active - so we're closing the program")
                    break
                logger.error("There was a LogIn Error {e} - You have still have {}/3 chances. "
                              "Please Re Enter Your LogIn Data".format(e, login_tryouts))
                whatcd_user = input("What.cd Username:")
                whatcd_pw = input("What.cd Password:")
                config['what-cd'] = {'use': True,
                                     'username': whatcd_user,
                                     'password': whatcd_pw}
                with open('artwork.ini', 'w') as configfile:
                    config.write(configfile)

    whatcd_api = ""
    
    if config['what-cd'].getboolean('use') is True and os.path.isfile("artwork.dat") is True:
        whatcd_cookies = pickle.load(open('artwork.dat', 'rb'))
        login_tryouts = 0
        while True:
            try:
                whatcd_api = whatapi.WhatAPI(username=config['what-cd']['username'],
                                             password=config['what-cd']['password'],
                                             cookies=whatcd_cookies)
                logger.info("LogIn into What.CD was sucessful")
                break
            except Exception as e:
                if login_tryouts >= 3:
                    logger.info("There seems to be some kind of error during logger in : {} - "
                                 "we won't use What.cd this time".format(e))
                    config['what-cd']['use'] = False
                    if config['iTunes'].getboolean('use') is False:
                        sys.exit("No iTunes and what.CD search is now active - so we're closing the script")
                    break
                login_tryouts += 1

    try:
        path = sys.argv[1]
        logger.info("Scans {}".format(path))
        folders_to_check = [path]
    except:
        path = input("Please Enter your Path you want to scan: ")
        folders_to_check = list((os.path.join(root, folder)
                                 for root, folders, files in os.walk(path) for folder in folders))
        folders_to_check.append(path)
    
    for folder in folders_to_check:
        audio = False
        artwork = False
        for file in os.listdir(os.path.join(path, folder)):
            if os.path.splitext(file)[1] in (".mp3", ".flac", ".m4a"):
                audio = True
                check_file = os.path.join(path, folder, file)
            if file.lower() in (config['folder']['jpgname'].lower()):
                artwork = True
            if audio is True and artwork is True:
                break
        
        if audio is True and artwork is True:
            logger.info("There's already artwork for {}".format(folder))
            continue
        
        if audio is True and artwork is False:
            if os.path.splitext(check_file)[1] == ".flac":
                try:
                    artist = FLAC(check_file)["artist"][0]
                except:
                    logger.error("Artist not tagged in folder {}".format(check_file))
                    artist = ""
                try:
                    album = FLAC(check_file)["album"][0]
                except:
                    logger.error("Album not tagged in folder {}".format(check_file))
                    album = ""

            if os.path.splitext(check_file)[1] == ".mp3":
                try:
                    artist = MP3(check_file)["artist"][0]
                except:
                    logger.error("Artist not tagged in folder {}".format(check_file))
                    artist = ""
                try:
                    album = MP3(check_file)["album"][0]
                except:
                    logger.error("Album not tagged in folder {}".format(check_file))
                    album = ""

            if os.path.splitext(check_file)[1] == ".m4a":
                try:
                    artist = MP4(check_file)["\xa9ART"]
                except KeyError:
                    logger.warning("Artist not tagged in folder {}".format(check_file))
                    artist = ""
                try:
                    album = MP4(check_file)["\xa9alb"]
                except:
                    logger.warning("Album not tagged in folder {}".format(check_file))
                    album = ""

            if album == "" and artist == "":
                logger.warning("Album isn't tagged at all, will skip: {}".format(check_file))
                continue
            
            logger.debug("Found the following information for {}: Artist: {} and Album: {}".format(check_file,
                                                                                                   artist,
                                                                                                   album))

            artwork_finder = ArtworkFinder(artist=str(artist),
                                           album=str(album),
                                           file=check_file,
                                           config=config,
                                           whatcdapi=whatcd_api)
            artwork_finder.get_artwork()
            
    logger.info("Done")
    input("Press Enter To Exit")
    sys.exit(0)


if __name__ == '__main__':
    if DEBUG:
        main()
    else:
        try:
            main()
        except KeyError as e:
            logger.info("Your config file is outdated for the current version of this script - "
                        "it's recommended to delete the 'artwork.ini' file to force the setup once again:{}".format(e))
            logger.info("Press Enter to Exit")
            sys.exit(1)
        except Exception as e:
            logger.info(Exception)
            logger.info("Unexpected Error - {}".format(e))
            input("Press Enter To Exit")
            sys.exit(1)