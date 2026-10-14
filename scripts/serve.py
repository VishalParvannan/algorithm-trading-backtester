"""Production entry point: provider PORT, one worker, no development reload."""
import os
import uvicorn


def settings():
    try:
        port=int(os.environ.get('PORT','8000'))
    except ValueError:
        raise ValueError('PORT must be a valid TCP port.') from None
    if not 1<=port<=65535:
        raise ValueError('PORT must be between 1 and 65535.')
    return dict(host='0.0.0.0',port=port,workers=1,reload=False)


if __name__=='__main__':
    uvicorn.run('backend.server:application',**settings())
