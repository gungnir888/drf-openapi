DEFAULT_ERROR_SCHEMA = {
    'properties': {
        'detail': {'type': 'string', 'description': 'Messaggio di errore'}
    }
}

METHOD_STATUS_CODES = {
    'GET': {
        'one': {
            'status_codes': [200],
            'error_codes': [401, 403, 404],
        },
        'many': {
            'status_codes': [200],
            'error_codes': [401, 403],
        }
    },
    'POST': {
        'one': {
            'status_codes': [201],
            'error_codes': [400, 401, 403],
        },
        'many': {
            'status_codes': [200],
            'error_codes': [400, 401, 403],
        }
    },
    'PATCH': {
        'one': {
            'status_codes': [200, 204],
            'error_codes': [400, 401, 403],
        },
        'many': {
            'status_codes': [200],
            'error_codes': [400, 401, 403],
        }
    },
    'PUT': {
        'one': {
            'status_codes': [202],
            'error_codes': [400, 401, 403],
        },
        'many': {
            'status_codes': [200],
            'error_codes': [400, 401, 403],
        }
    },
    'DELETE': {
        'one': {
            'status_codes': [204],
            'error_codes': [400, 401, 403, 406],
        },
        'many': {
            'status_codes': [200],
            'error_codes': [400, 401, 403],
        }
    },
}


STATUS_CODES_RESPONSES = {
    200: {
        'description': 'Successful'
    },
    201: {
        'description': 'Created'
    },
    202: {
        'description': 'Update Accepted'
    },
    204: {
        'description': 'Empty Content',
        'content': False
    },
    400: {
        'description': 'Invalid Content'
    },
    401: {
        'description': 'Unauthorized'
    },
    403: {
        'description': 'Forbidden'
    },
    404: {
        'description': 'Not Found'
    },
    406: {
        'description': 'Not Acceptable',
        'content': False
    },
    500: {
        'description': 'Internal Server Error'
    },
    502: {
        'description': 'Bad Gateway'
    }
}


class RemovedInDRF313Warning(DeprecationWarning):
    pass


class RemovedInDRF314Warning(PendingDeprecationWarning):
    pass
