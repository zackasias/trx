import os
import json
import logging
from datetime import timedelta, datetime

from utils.utils import create_requests_session


class BeatportApi:
    def __init__(self):
        self.API_URL = 'https://api.beatport.com/v4/'
        self.AUTH_URL = 'https://account.beatport.com'
        
        # Mobile app client details
        self.client_id = '5yfTsQ6B31nNXPsImGyeZiZ6oDzDiwG50E7FS92j'
        
        self.access_token = None
        self.refresh_token = None 
        self.expires = None
        
        self.s = create_requests_session()
        
        # Setup debug logging
        debug_dir = 'debug'
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir)
        
        self.debug_log = logging.getLogger('beatport_debug')
        self.debug_log.setLevel(logging.DEBUG)
        self.debug_log.propagate = False  # Prevent duplicate logging
        
        # Only add handler if it doesn't exist
        if not self.debug_log.handlers:
            # Add file handler for debug logging
            fh = logging.FileHandler(os.path.join(debug_dir, 'beatport_auth_debug.log'))
            fh.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(message)s')
            fh.setFormatter(formatter)
            self.debug_log.addHandler(fh)
        else:
            print("self.debug_log.handlers does not exist")

    def headers(self, use_access_token: bool = False):
        headers = {
            'Accept-Encoding': 'gzip',
            'Connection': 'Keep-Alive',
            'User-Agent': 'okhttp/4.12.0'
        }
        if use_access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        return headers

    def _log_request_response(self, method, url, headers, data=None, response=None):
        """Log request and response details"""
        self.debug_log.debug(f"\nREQUEST:")
        self.debug_log.debug(f"METHOD: {method}")
        self.debug_log.debug(f"URL: {url}")
        self.debug_log.debug("HEADERS:")
        for k, v in headers.items():
            if k.lower() == 'authorization':
                v = v[:50] + '...' if v else v  # Truncate auth token
            self.debug_log.debug(f"{k}: {v}")
        
        if data:
            self.debug_log.debug("\nREQUEST BODY:")
            try:
                self.debug_log.debug(json.dumps(data, indent=2))
            except:
                self.debug_log.debug(str(data))

        if response:
            self.debug_log.debug("\nRESPONSE:")
            self.debug_log.debug(f"STATUS: {response.status_code}")
            self.debug_log.debug("HEADERS:")
            for k, v in response.headers.items():
                self.debug_log.debug(f"{k}: {v}")
            self.debug_log.debug("\nRESPONSE BODY:")
            try:
                self.debug_log.debug(json.dumps(response.json(), indent=2))
            except:
                self.debug_log.debug(response.text)

    def auth(self, username: str, password: str) -> dict:
        """Mobile app authentication flow with detailed logging"""
        # Step 1: Login with credentials
        login_url = f'{self.AUTH_URL}/identity/v1/login/'
        login_headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip',
            'Connection': 'Keep-Alive',
            'Content-Type': 'application/json',
            'User-Agent': 'okhttp/4.12.0'
        }
        login_data = {
            'username': username,
            'password': password
        }
        
        self._log_request_response('POST', login_url, login_headers, login_data)
        
        r = self.s.post(login_url, json=login_data, headers=login_headers)
        
        self._log_request_response('POST', login_url, login_headers, login_data, r)

        if r.status_code != 200:
            return r.json()

        # Step 2: Get authorization code
        code_verifier = 'zSpnef_Xs38AF8ZTW7N3ENkaD506wawhvLyDSNdNEB8'
        code_challenge = 'VxE9bAsvWy4U2PZvlEepiUsg5JHpk8P968owhKDjGFY'
        
        auth_url = f'{self.AUTH_URL}/o/authorize/'
        auth_params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'redirect_uri': 'beatport://bp_mobile_oauth'
        }
        auth_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip',
            'Connection': 'Keep-Alive',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; sdk_gphone64_arm64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Mobile Safari/537.36'
        }
        
        self._log_request_response('GET', auth_url, auth_headers)
        
        r = self.s.get(auth_url, params=auth_params, headers=auth_headers, allow_redirects=False)
        
        self._log_request_response('GET', auth_url, auth_headers, response=r)

        if r.status_code != 302:
            return {'error_description': 'Failed to get authorization code'}
            
        auth_code = r.headers['location'].split('code=')[1]
        
        # Step 3: Exchange code for tokens
        token_url = f'{self.AUTH_URL}/o/token/'
        token_data = {
            'client_id': self.client_id,
            'code_verifier': code_verifier,
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'beatport://bp_mobile_oauth'
        }
        token_headers = {
            'Accept-Encoding': 'gzip',
            'Connection': 'Keep-Alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'okhttp/4.12.0'
        }
        
        self._log_request_response('POST', token_url, token_headers, token_data)
        
        r = self.s.post(token_url, data=token_data, headers=token_headers)
        
        self._log_request_response('POST', token_url, token_headers, token_data, r)

        if r.status_code != 200:
            return r.json()

        data = r.json()
        self.access_token = data['access_token']
        self.refresh_token = data['refresh_token']
        self.expires = datetime.now() + timedelta(seconds=data['expires_in'])

        return data

    def refresh(self):
        """Refresh access token"""
        r = self.s.post(f'{self.AUTH_URL}/o/token/',
            data={
                'client_id': self.client_id,
                'refresh_token': self.refresh_token,
                'grant_type': 'refresh_token'
            },
            headers={
                'Accept-Encoding': 'gzip',
                'Connection': 'Keep-Alive',
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'okhttp/4.12.0'
            })

        if r.status_code != 200:
            return r.json()

        data = r.json()
        self.access_token = data['access_token']
        self.refresh_token = data['refresh_token']
        self.expires = datetime.now() + timedelta(seconds=data['expires_in'])
        return data

    def set_session(self, session: dict):
        self.access_token = session.get('access_token')
        self.refresh_token = session.get('refresh_token')
        self.expires = session.get('expires')

    def get_session(self):
        return {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expires': self.expires
        }

    def _get(self, endpoint: str, params: dict = None):
        """Add logging to GET requests"""
        if not params:
            params = {}
            
        url = f'{self.API_URL}{endpoint}'
        headers = self.headers(use_access_token=True)
        
        self._log_request_response('GET', url, headers)
        
        r = self.s.get(url, params=params, headers=headers)
        
        self._log_request_response('GET', url, headers, response=r)

        if r.status_code == 401:
            raise ValueError(r.text)

        if r.status_code not in {200, 201, 202}:
            raise ConnectionError(r.text)

        return r.json()

    def get_account(self):
        return self._get('auth/o/introspect')

    def get_track(self, track_id: str):
        return self._get(f'catalog/tracks/{track_id}')

    def get_release(self, release_id: str):
        return self._get(f'catalog/releases/{release_id}')

    def get_release_tracks(self, release_id: str, page: int = 1, per_page: int = 100):
        return self._get(f'catalog/releases/{release_id}/tracks', params={
            'page': page,
            'per_page': per_page
        })

    def get_playlist(self, playlist_id: str):
        return self._get(f'catalog/playlists/{playlist_id}')

    def get_playlist_tracks(self, playlist_id: str, page: int = 1, per_page: int = 100):
        return self._get(f'catalog/playlists/{playlist_id}/tracks', params={
            'page': page,
            'per_page': per_page
        })

    def get_chart(self, chart_id: str):
        return self._get(f'catalog/charts/{chart_id}')

    def get_chart_tracks(self, chart_id: str, page: int = 1, per_page: int = 100):
        return self._get(f'catalog/charts/{chart_id}/tracks', params={
            'page': page,
            'per_page': per_page
        })

    def get_artist(self, artist_id: str):
        return self._get(f'catalog/artists/{artist_id}')

    def get_artist_tracks(self, artist_id: str, page: int = 1, per_page: int = 100):
        return self._get(f'catalog/artists/{artist_id}/tracks', params={
            'page': page,
            'per_page': per_page
        })

    def get_label(self, label_id: str):
        return self._get(f'catalog/labels/{label_id}')

    def get_label_releases(self, label_id: str):
        return self._get(f'catalog/labels/{label_id}/releases')

    def get_search(self, query: str):
        return self._get('catalog/search', params={'q': query})

    def get_track_stream(self, track_id: str):
        """Get HLS stream URL for a track"""
        return self._get(f'catalog/tracks/{track_id}/stream/')

    def get_track_download(self, track_id: str, quality: str):
        """Get direct download URL for a track"""
        return self._get(f'catalog/tracks/{track_id}/download', params={'quality': quality})

    def get_subscription(self):
        """Get user's subscription status"""
        return self._get('my/subscriptions')

    def setup_account(self):
        """Initial account setup sequence"""
        try:
            # Initial discover page request
            self._get('curation/discover-page-modules/', params={'items': 'true'})
            
            # First PATCH to my/account/
            self._patch('my/account/')
            
            # Second PATCH with same data
            self._patch('my/account/')
            
            # Third PATCH (seems to be a retry/confirmation)
            self._patch('my/account/')
            
            # Get discover page modules again
            self._get('curation/discover-page-modules/', params={'items': 'true'})
            
            # Get account info
            account_info = self._get('my/account/')
            
            # Get subscriptions
            subscription = self._get('my/subscriptions/')
            
            try:
                # Try push notification subscription but don't fail if it errors
                self._post('my/push-notifications/subscribe/', data={
                    'token': 'fcm-token',
                    'subscribe': True,
                    'platform': 'android'
                })
            except:
                pass  # Ignore any push notification errors
                
            # Final discover page modules request
            self._get('curation/discover-page-modules/', params={'items': 'true'})
            
            return account_info, subscription
        except Exception as e:
            logging.error(f"Error in setup_account: {str(e)}")
            raise

    def _patch(self, endpoint: str, data: dict = None):
        """Handle PATCH requests with logging"""
        if endpoint == 'my/account/':
            # Set default preferences for mobile app
            data = {
                "preferences": {
                    "mobile_push_notification_is_enabled": True,
                    "mobile_push_notification_settings": {
                        "my_beatport_artists": True,
                        "my_beatport_labels": True
                    }
                }
            }
        
        headers = self.headers(use_access_token=True)
        headers['Content-Type'] = 'application/json; charset=UTF-8'
        
        url = f'{self.API_URL}{endpoint}'
        
        self._log_request_response('PATCH', url, headers, data)
        
        r = self.s.patch(url, json=data, headers=headers)
        
        self._log_request_response('PATCH', url, headers, data, r)
        
        if r.status_code == 401:
            raise ValueError(r.text)
        
        if r.status_code not in {200, 201, 202}:
            raise ConnectionError(r.text)
        
        return r.json() if r.text else None

    def _post(self, endpoint: str, data: dict = None):
        """Handle POST requests with logging"""
        headers = self.headers(use_access_token=True)
        headers['Content-Type'] = 'application/json; charset=UTF-8'
        
        # Skip push notification if data is missing
        if endpoint == 'my/push-notifications/subscribe/' and not data:
            return None
        
        url = f'{self.API_URL}{endpoint}'
        
        self._log_request_response('POST', url, headers, data)
        
        r = self.s.post(url, json=data, headers=headers)
        
        self._log_request_response('POST', url, headers, data, r)
        
        if r.status_code == 401:
            raise ValueError(r.text)
        
        # Allow 400 for push notification endpoint
        if endpoint == 'my/push-notifications/subscribe/' and r.status_code == 400:
            return None
        
        if r.status_code not in {200, 201, 202}:
            raise ConnectionError(r.text)
        
        return r.json() if r.text else None

    def get_stream_url(self, track_id):
        """Get streaming URL for a track"""
        url = f"{self.API_URL}catalog/tracks/{track_id}/stream/"
        headers = self.headers(use_access_token=True)
        
        self._log_request_response('GET', url, headers)
        
        response = self.s.get(url, headers=headers)
        
        self._log_request_response('GET', url, headers, response=response)
        
        if response.status_code != 200:
            raise Exception(f"Failed to get stream URL: {response.text}")
        
        data = response.json()
        return data
