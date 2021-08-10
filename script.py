import time
import subprocess
import sys
import json

apikey = 'uJfTlXwih6'
# apikey = 'v8pQ6oyB'

# flac = '/usr/local/bin/flac'
flac = '/usr/bin/flac'
# metaflac = '/usr/local/bin/metaflac'
metaflac = '/usr/bin/metaflac'
# fpcalc = '/usr/local/bin/fpcalc'
fpcalc = '/usr/bin/fpcalc'

def pad_directory_name(path):
    if(path[len(path) - 1] != '/'):
         return path + '/'

    return path

def create_working_path(path):
    working_path = path + '../tagged-flac/'
    cp = subprocess.run(['/bin/cp', '-R', path, working_path])
    return working_path

def get_flac_files(path):
    ls = subprocess.run(['/bin/ls', path], capture_output=True)
    files = str_from_bitstream(ls.stdout).split('\\n')
    flac_files = []
    for filename in files:
        if(filename.find('flac') > -1):
            flac_files.append(filename)
        #
    #
    return flac_files

def create_acoustid_url(duration, fingerprint):
    return 'https://api.acoustid.org/v2/lookup?meta=recordings+releasegroups+releases+tracks+compress+sources&duration=' + duration + '&fingerprint=' + fingerprint + '&client=' + apikey + '&format=json'

def str_from_bitstream(bitstream):
    string = str(bitstream)
    return string[slice(2, len(string) - 1)]

def get_acoustid_json(url):
    acoustid_json = None;
    while(acoustid_json is None):
        curl = subprocess.run(['/usr/bin/curl', url], capture_output=True)
        print(curl.stdout)
        curl_output = str_from_bitstream(curl.stdout)
        if(curl_output.find('error') == -1):
            acoustid_json = curl_output
            print(acoustid_json)
        else:
            print('error occured--trying again in one second')
            print(curl_output)
            time.sleep(1)


    return acoustid_json

def get_track_number(filename):
    print(filename)
    return int(filename.split('.')[0])

def escape_string_for_metaflac(str):
#    return str.replace(' ', '\ ').replace(';', '\;')
    return str

def try_identify_track(acoustid_response, track_number, album_blacklist=[], match_track_number=True):
    for result in acoustid_response:
        for recording in result['recordings']:
            for releasegroup in recording['releasegroups']:
                for release in releasegroup['releases']:
                    for medium in release['mediums']:
                        for track in medium['tracks']:
                            print(track['position'])
                            if(not match_track_number or track['position'] == track_number):
                                album_name = releasegroup['title']
                                album_id = release['id']
                                if(album_id in album_blacklist):
                                    continue

                                track_name = recording['title']
                                full_artist = ''
                                for artist in releasegroup['artists']:
                                    full_artist = full_artist + artist['name']
                                    if('joinphrase' in artist):
                                        full_artist = full_artist + artist['joinphrase']


                                year = 'unknown year :('
                                if('date' in release and 'year' in release['date']):
                                    year = str(release['date']['year'])

                                album_track_count = str(release['track_count'])
                                print(track_name + ' | ' + album_name + ' | ' + full_artist + ' | ' + year + ' | ' + str(track_number) + '/' + album_track_count)
                                track_identified = True
                                return {
                                    'album_name': escape_string_for_metaflac(album_name),
                                    'album_id': escape_string_for_metaflac(album_id),
                                    'track_name': escape_string_for_metaflac(track_name),
                                    'full_artist': escape_string_for_metaflac(full_artist),
                                    'year': escape_string_for_metaflac(year),
                                    'album_track_count': escape_string_for_metaflac(album_track_count)
                                }
                            #
                        #
                    #
                #
            #
        #
    # whitespace ends here
    return 'track not identified'

def identify_track(path, filename, track_number, album_blacklist=[]):
    fpcalc = subprocess.run(['fpcalc', path + filename], capture_output=True)
    fpcalc_output = str_from_bitstream(fpcalc.stdout).split('\\n')
    duration = fpcalc_output[0].replace('DURATION=', '')
    fingerprint = fpcalc_output[1].replace('FINGERPRINT=', '')
    url = create_acoustid_url(duration, fingerprint);
    acoustid_json = get_acoustid_json(url)
    print(acoustid_json)
    acoustid_response = json.loads(acoustid_json)['results']
    track_identity = 'track not identified'
    match_track_number = True
    track_identity = try_identify_track(acoustid_response, track_number, album_blacklist)
    if(track_identity == 'track not identified'):
        track_identity = try_identify_track(acoustid_response, track_number, album_blacklist, False)

    return track_identity
def get_track_identities(path, flac_files, album_blacklist=[]):
    track_identities = {}
    for filename in flac_files:
        track_number = get_track_number(filename)
        time.sleep(1)
        track_identities[filename] = identify_track(path, filename, track_number, album_blacklist)

    return track_identities

def get_album_counts(flac_files, track_identities):
    album_counts = {'ids_to_names': {}, 'names_to_ids': {}}
    for filename in flac_files:
        specific_album_id = track_identities[filename]['album_id']
        specific_album_name = track_identities[filename]['album_name']
        if(specific_album_id in album_counts):
            album_counts[specific_album_id] = album_counts[specific_album_id] + 1
        else:
            album_counts[specific_album_id] = 1
            album_counts['ids_to_names'][specific_album_id] = specific_album_name
            album_counts['names_to_ids'][specific_album_name] = specific_album_id
        #
    #
    return album_counts

def get_album_art(album_id, path):
    print('https://coverartarchive.org/release/' + album_id)
    curl0 = subprocess.run(['/usr/bin/curl', '-L', 'https://coverartarchive.org/release/' + album_id], capture_output=True)
    curl0_json = str_from_bitstream(curl0.stdout)
    art_link = json.loads(curl0_json)['images'][0]['image']
    curl1 = subprocess.run(['/usr/bin/curl', '-L', art_link, '--output', path + 'art.jpg'])
    return path + 'art.jpg'

def tag_tracks(path, flac_files, art_path, track_identities):
    for filename in flac_files:
        filepath = path + filename
        add_image_art = subprocess.run([flac, '-f', filepath, '--picture=' + art_path])
        create_vorbis_comment = subprocess.run([metaflac, '--remove-tag=ARTIST', '--remove-tag=ALBUM', '--remove-tag=TITLE', '--remove-tag=DATE', '--set-tag=ARTIST=' + track_identities[filename]['full_artist'], '--set-tag=ALBUM=' + track_identities[filename]['album_name'], '--set-tag=TITLE=' + track_identities[filename]['track_name'], '--set-tag=DATE=' + track_identities[filename]['year'], filepath])
        print(add_image_art)
        print(create_vorbis_comment)
        
    return

path = sys.argv[1]
path = pad_directory_name(path)
print(path)
print('creating new working directory:')
working_path = create_working_path(path)
flac_files = get_flac_files(working_path)
'''
flac_files = get_flac_files(path)
print(flac_files)
identify_track(path, flac_files[0], 1)
'''
track_identities = get_track_identities(working_path, flac_files)
album_counts = get_album_counts(flac_files, track_identities)

album_ids = []
for album_id in album_counts['ids_to_names']:
    album_ids.append(album_id)

while(len(album_counts.keys()) > 3):
    print('uh oh')
    # print('here is the track data:')
    # print(json.dumps(track_identities))
    print('choose one of the following albums:')
    counter = 0
    album_ids = []
    for album_id in album_counts['ids_to_names']:
        album_name = album_counts['ids_to_names'][album_id]
        print('[' + str(counter) + '] ' + album_id + ' '+ album_name)
        album_ids.append(album_id)
        counter = counter + 1
        
    response = int(input('correct album: ').replace('\n', ''))
    album_blacklist = []
    for album in album_ids:
        if(album_id != album_ids[response]):
            album_blacklist.append(album_id)
        #
    #
    album_ids[0] = album_ids[response]
    track_identities = get_track_identities(working_path, flac_files, album_blacklist)
    album_counts = get_album_counts(flac_files, track_identities)

album_id = album_ids[0]
art_path = get_album_art(album_id, working_path)
tag_tracks(working_path, flac_files, art_path, track_identities)
print('done!')
print(json.dumps(track_identities))

