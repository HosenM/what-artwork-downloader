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

def installPackage(Package):
    import pip
    try:
        pip.main(['install','--upgrade',Package])
    except Exception as e:
        sys.exit("Couldn't install {} with pip - {}".format(Package,e))
    

try:
    import requests
except ImportError:
    logging.warning("Requests is not installed - will try to install it now via pip")
    installPackage("requests")
    try:
        import requests
    except ImportError as e:
        sys.exit("Failed to install requests - {}".format(e))

try:
    from PIL import Image
except ImportError:
    logging.warning("Pillow is not installed - will try to install it now via pip")
    installPackage("Pillow")
    try:
        from PIL import Image
    except ImportError as e:
        sys.exit("Failed to install Pillow - {}".format(e))

try:
    import whatapi
except ImportError:
    logging.warning("WhatAPI is not installed - will try to install it now via pip")
    installPackage("https://github.com/capital-G/whatapi/tarball/master")
    try:
        import whatapi
    except ImportError as e:
        sys.exit("Failed to install WhatAPI - {}".format(e))

try:
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.easyid3 import EasyID3 as MP3
except ImportError:
    logging.warning("mutagen is not installed - will try to install it now via pip")
    installPackage("mutagen")
    try:
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
        from mutagen.easyid3 import EasyID3 as MP3
    except ImportError as e:
        sys.exit("Failed to install mutagen - {}".format(e))

    

logging.basicConfig(level=logging.ERROR)


class ArtworkFinder():
    def __init__(self,config,whatcdapi,**kwargs):
        self._config = config
        self._whatcdapi = whatcdapi
        self._artist = kwargs.get("artist")
        self._album = kwargs.get("album")
        self._entity = kwargs.get("entity","album")
        self._country = kwargs.get("country","us")
        self._path = os.path.dirname(kwargs.get("file"))
        self._source = ""
        
        VariousArtists = ("various", "artists" ,"{","}","[","]","the ",",","(",")")
        for various in VariousArtists:
            self._artist = self._artist.lower().replace(various.lower()," ")
        
        if "various artists" in self._path.lower():
            self._artist = ""
        
        self._album = ''.join([i for i in self._album if not i.isdigit()])
        
        VariousAlbums = ("(",")","CD","Deluxe","Edition","Remaster","Remastered","SACD","MP3","FLAC","}","{","[","]",",","!",";","(",")","!","#",".","-","/","disk","disq","disc ","bonus","dvd")
        for various in VariousAlbums:
            self._album = self._album.lower().replace(various.lower()," ")
        
        
        self._name = self._artist+" "+self._album
        
    
    def getArtwork(self):
        if self._config['iTunes'].getboolean('use'):
            iTunesAPIResults = self.iTunesAPI()
            if iTunesAPIResults:
                storesucess = self.store()
                if storesucess == False:
                    logging.info("No Artwork found in iTunes for {}".format(self._path))
                    print("No Artwork found in iTunes for {} - {} in {}".format(self._artist.title(),self._album.title(),self._path))
                    return False
                logging.info("Sucessfully saved the iTunes Artwork for {} - {} in the folder {}".format(self._artist, self._album, self._path))
                print("Saved iTunes Artwork for {} - {} in {}".format(self._artist.title(),self._album.title(),self._path))
                return True
            else:
                logging.info("No Artwork found in iTunes for {}".format(self._path))
                print("No Artwork found in iTunes for {} - {} in {}".format(self._artist.title(),self._album.title(),self._path))
        
        if self._config['what-cd'].getboolean('use'):
            whatCDAPIresults = self.whatCDAPI()
            if whatCDAPIresults:
                storesucess = self.store()
                if storesucess == False:
                    logging.info("No Artwork found in what.CD for {}".format(self._path))
                    print("No Artwork found in what.CD for {} - {} in {}".format(self._artist.title(),self._album.title(),self._path))
                    return False
                logging.info("Sucessfully saved the what.CD Artwork for {} - {} in the folder {}".format(self._artist, self._album, self._path))
                print("Saved what.CD Artwork for {} - {} in {}".format(self._artist.title(),self._album.title(),self._path))
                return True
            else:
                logging.info("No Artwork found in what.CD for {}".format(self._path))
                print("No Artwork found in what.CD for {} - {} in {}".format(self._artist.title(),self._album.title(),self._path))
        
        return False
    
    def iTunesAPI(self):
        requestparams = {'term':self._name,'entity':self._entity,'country':self._country}
        
        try:
            self._request = requests.get("http://ax.itunes.apple.com/WebObjects/MZStoreServices.woa/wa/wsSearch",params = requestparams)
        except requests.exceptions.Timeout:
            logging.error("No connection to iTunes API - check your Internet connection")
            return False
        
        if self._request.status_code != 200:
            logging.error("Error from iTunes API - Error Code {} - {}".format(self._request.status_code, self._request.text))
            return False
        
        if (len(self._request.json()['results'])==0):
            logging.info("No search results  in iTunes for {}".format(self._name))
            return False
        
        self._highresURL = self._request.json()['results'][0].get('artworkUrl100').replace("100x100","1200x1200")
        self._normresURL = self._request.json()['results'][0].get('artworkUrl100').replace("100x100","600x600")
        
        logging.info("Found iTunes Artwork for {}, - {}".format(self._name, self._highresURL))
        
        self._source = "iTunes"
        return True
    
    def whatCDAPI(self):
        #time.sleep(2) # in order to don't storm the whatCD API
        whatrequest = self._whatcdapi.request("browse",searchstr=self._name)
        if len(whatrequest['response']['results']) == 0:
            logging.info("No What.CD results for {} - {}".format(self._artist,self._album))
            return False
        try:
            self._highresURL = whatrequest['response']['results'][0]['cover']
        except KeyError:
            logging.info("Found a What-CD Release but without cover")
            return False
        
        if self._highresURL  == "":
            logging.info("Found a What-CD Release but without cover")
            return False
        
        logging.info("Found what.CD Artwork for {}, - {}".format(self._name, self._highresURL))
        self._source = "whatCD"
        return True
        
    def store(self):
        logging.debug("Cover-URL: {}".format(self._highresURL))
        
        downloader = urllib.request.build_opener()
        downloader.addheaders = [('User-agent', 'Mozilla/5.0')] #avoid problems with whatIMG
        try:
            with downloader.open(self._highresURL) as response, open(os.path.join(self._path,self._highresURL.split("/")[-1]), "wb") as out_file:
                shutil.copyfileobj(response, out_file)
        except:
            logging.error("Couldn't write HighRes Artwork for {} - URL is {}".format(self._path, self._highresURL))
            return False
        
        
        if os.path.splitext(self._highresURL.split("/")[-1])[1] not in (".jpg",".jpeg"):
            logging.info("The downloaded Artwork {} is not .jpg or .jpeg, so we will convert it to .jpg now".format(self._highresURL.split("/")[-1]))
            im = Image.open(os.path.join(self._path,self._highresURL.split("/")[-1])).convert('RGB')
            im.save(os.path.join(self._path,self._config['folder']['jpgname']))
            os.remove(os.path.join(self._path,self._highresURL.split("/")[-1]))
        else:
            os.rename(os.path.join(self._path,self._highresURL.split("/")[-1]),os.path.join(self._path,self._config['folder']['jpgname']))
        
        

def main():
    
    print("Welcome to artwork.py")
    
    config = configparser.ConfigParser()
    
    if os.path.isfile('artwork.ini') is False:
        if os.path.isfile('artwork.dat') is True:
            os.remove("artwork.dat")
        print("SETUP")
        while True:
            userinput = input("Do you want to use iTunes as Database? (Y/N)")
            if userinput.lower() == "y":
                config['iTunes'] = {'use':True}
                break
            elif userinput.lower() == "n":
                config['iTunes'] = {'use':False}
                break
        while True:
            userinput = input("Do you want to use What.CD as Database? (Y/N)")
            if userinput.lower() == "y":
                print("OK, for that we will need your What-CD login")
                whatcduser = input("What.cd Username:")
                whatcdpw = input("What.cd Password:")
                config['what-cd'] = {'use':True,'username':whatcduser,'password':whatcdpw}
                break
            if userinput.lower() == "n":
                config['what-cd'] = {'use':False}
                break
        if config['iTunes'].getboolean('use') is False and config['what-cd'].getboolean('use') is False:
            sys.exit("Sorry, you must select at least one of the two choices - Goobye")
        
        while True:
            folderinput = input("Do you want to use something else as folder.jpg? (Y/N)")
            if folderinput.lower() == "n":
                config['folder'] = {'jpgname':'folder.jpg'}
                break
            if folderinput.lower() == "y":
                jpgname = input("Ok, then enter your desired name")
                if not "." in jpgname:
                    jpgname = jpgname+".jpg"
                config['folder'] = {'jpgname':jpgname}
                break
        
        with open('artwork.ini','w') as configfile:
            config.write(configfile)
        
        print("Setup Sucessful - if you wan't to run this setup again, simply delete the artwork.ini file or modify it for your needs")
        
    else:
        config.read('artwork.ini')
           
    if config['what-cd'].getboolean('use') is True and os.path.isfile("artwork.dat") is False:
        print("There's no cookie for your What.cd Login - so we will have to login you")
        logintryouts = 0
        while True:
            try:
                whatcdapi = whatapi.WhatAPI(username=config['what-cd']['username'], password = config['what-cd']['password'])
                pickle.dump(whatcdapi.session.cookies, open('artwork.dat', 'wb'))
                break

            except Exception as e:
                logintryouts += 1
                if logintryouts > 3:
                    print("It seems What-CD is down, so we won't use that now this time")
                    config['what-cd'] = {'use':False}
                    if config['iTunes'].getboolean('use') == False:
                        sys.exit("No iTunes and what.CD search is now active - so we're closing the program")
                    break
                print("There was a LogIn Error {e} - You have still have {}/3 chances. Please Re Enter Your LoigIn Data".format(e,logintryouts))
                whatcduser = input("What.cd Username:")
                whatcdpw = input("What.cd Password:")
                config['what-cd'] = {'use':True,'username':whatcduser,'password':whatcdpw}
                with open('artwork.ini','w') as configfile:
                    config.write(configfile)

    whatcdapi = ""
    
    if config['what-cd'].getboolean('use') is True and os.path.isfile("artwork.dat") is True:
        whatcdcookies = pickle.load(open('artwork.dat','rb'))
        logintryouts = 0
        while True:
            try:
                whatcdapi = whatapi.WhatAPI(username = config['what-cd']['username'], password=config['what-cd']['password'], cookies = whatcdcookies)
                print("LogIn into What.CD was sucessful")
                break
            except Exception as e:
                if logintryouts >= 3:
                    print("There seems to be some kind of error during logging in : {} - we won't use What.cd this time".format(e))
                    config['what-cd']['use'] = False
                    if config['iTunes'].getboolean('use') == False:
                        sys.exit("No iTunes and what.CD search is now active - so we're closing the program")
                    break
                logintryouts += 1 
    
    path = input("Please Enter your Path you want to scan:")
        
    for folder in (os.path.join(root, folder) for root, folders, files in os.walk(path) for folder in folders):
        audio = False
        artwork = False
        for file in os.listdir(os.path.join(path,folder)):
            if os.path.splitext(file)[1] in (".mp3", ".flac", ".m4a"):
                audio = True
                examplefile = os.path.join(path,folder,file)
            if file.lower() in (config['folder']['jpgname'].lower()):
                artwork = True
            if audio == True and artwork == True:
                break
        
        if audio == True and artwork == True:
            logging.info("There's already artwork for {}".format(folder))
            continue
        
        if audio == True and artwork != True:
            if os.path.splitext(examplefile)[1] == ".flac":
                try:
                    artist = FLAC(examplefile)["artist"][0]
                except:
                    logging.error("Artist not tagged in folder {}".format(examplefile))
                    artist = ""
                try:
                    album = FLAC(examplefile)["album"][0]
                except:
                    logging.error("Album not tagged in folder {}".format(examplefile))
                    album = ""
                
                
            if os.path.splitext(examplefile)[1] == ".mp3":
                try:
                    artist = MP3(examplefile)["artist"][0]
                except:
                    logging.error("Artist not tagged in folder {}".format(examplefile))
                    artist = ""
                try:
                    album = MP3(examplefile)["album"][0]
                except:
                    logging.error("Album not tagged in folder {}".format(examplefile))
                    album = ""
                
            
            if os.path.splitext(examplefile)[1] == ".m4a":
                try:
                    artist = MP4(examplefile)["\xa9ART"]
                except KeyError:
                    logging.warning("Artist not tagged in folder {}".format(examplefile))
                    artist = ""
                try:
                    album = MP4(examplefile)["\xa9alb"]
                except:
                    logging.warning("Album not tagged in folder {}".format(examplefile))
                    album = ""
                
            

            if album == "" and artist == "":
                logging.warning("Album isn't tagged at all: {}".format(examplefile))
                continue
            
            logging.info("Found the following information for {}: Artist: {} and Album: {}".format(examplefile,artist,album))
            
            getArtwork = ArtworkFinder(artist = str(artist), album = str(album), file = examplefile, config = config, whatcdapi = whatcdapi)
            getArtwork.getArtwork()
            
    print("Done")


if __name__ == '__main__':
    main()