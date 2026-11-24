from orbit.dashboard import exceptions

PANEL = 'orbs'
PANEL_DASHBOARD = 'project'
PANEL_GROUP = 'orbit'
ADD_PANEL = 'orbit.dashboard.orbs.panel.Orbs'
ADD_INSTALLED_APPS = ['orbit.dashboard']
ADD_JS_FILES = ['orbit/orbs-live.js']
ADD_SCSS_FILES = ['orbit/orbs.scss']

ADD_EXCEPTIONS = {
    'unauthorized': (exceptions.OrbitUnauthorized,),
    'not_found': (exceptions.OrbNotFound,),
    'recoverable': (exceptions.OrbitError,),
}
