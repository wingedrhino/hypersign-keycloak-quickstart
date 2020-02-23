# HyperSign KeyCloak Docker Quickstart

This project would help you quickly setup a Dockerized KeyCloak with the
HyperSign plugin pre-loaded and ready to go! It is written for use with
`docker-compose`. But we'll eventually also make this forwards compatible with
Kubernetes!

To know more about **Hypersign**, please visit
[this](https://github.com/hypermine-bc/hypersign/blob/master/docs/overview.md).

## Installation

### Setup Docker

install [docker](https://docs.docker.com/install/linux/docker-ce/ubuntu) and
[docker-compose](https://docs.docker.com/compose/install/).

### Git Clone

Clone this repository.

```sh
git clone https://github.com/wingedrhino/hypersign-keycloak-quickstart.git 
cd hypersign-keycloak-quickstart 
```

### Set HS_CLIENT_ALIAS

Set the `HS_CLIENT_ALIAS` in `docker-compose.yml`. This identifies your KeyCloak
and HyperSign secured application uniquely. Default value: `hs_playground`.

### Set HS_REDIRECT_URI

Set `HS_REDIRECT_URI` in `docker-compose.yml`. This is the URL to which KeyCloak
shall redirect you to after a successful login. It should be the endpoint of
your frontend application. For example, `http://localhost:8000` is the included
default for regular everyday web development.

### Run HyperSign Powered KeyCloak via Docker Compose!

```sh
docker-compose up -d
```

## Extra Configuration

The included `docker-compose.yml` has a bunch of other environment variables
passed to the KeyCloak container that you can play with. The file is
self-documenting.

## Post-Installation

### Ports Used

On successfully execution of the script, you should be able to see  three
containers running in your machine (run `docker-compose ps`).
- A keycloak server at port `8080`
- A postgres database server at port `5432`
- A hs-auth server at port `3000`


**Management portal**

Although, the basic configurations for identity and access management is already
done once all containers run successfully, you (the admin) will get a
*Management portal* at `http://localhost:8080` for managing advance identity
related configurations like groups, users, roles, scope etc. The default
credentials for admin user is: Username: `admin`, Password: `admin`.

You can configure ports and credentials for management portal as per your
convenience in the docker-compose file, present in the root directory of this
repository. In future versions you shall be able to do that using the cli
itself.

## Example Usage with Node.js

Now that every thing is installed and setup, let's see how to use Hypersign in
your project. We will take example of _securing APIs written in Node js_.

- Make node js project with `express` and copy `keycloak.json` file from
`data-template` folder into the root directory of your project.

```json
{
    "realm": "master",
    "auth-server-url": "http://localhost:8080/auth/",
    "ssl-required": "external",
    "resource": "node-js-client-app",
    "public-client": true,
    "confidential-port": 0
}
```

- Install `keycloak-connect` and `express-session` libraries from npm
- Add `app.js` with following code:

```javascript
'use strict';
const Keycloak = require('keycloak-connect');
const express = require('express');
const session = require('express-session');
const app = express();

var memoryStore = new session.MemoryStore();
var keycloak = new Keycloak({ store: memoryStore });

//session
app.use(session({
  secret:'this_should_be_long_text',
  resave: false,
  saveUninitialized: true,
  store: memoryStore
}));

app.use(keycloak.middleware());

//route protected with Keycloak
app.get('/test', keycloak.protect(), function(req, res){
  res.send("This is protected");
});

//unprotected route
app.get('/',function(req,res){
  res.send("This is public");
});

app.use( keycloak.middleware( { logout: '/'} ));

app.listen(8000, function () {
  console.log('Listening at http://localhost:8000');
});

```
- Run the server using `node app.js`. The server (client's) will start running
on `http://localhost:8000`

Try accessing `/` endpoint, you will get the response `This is public`
immediately. Whereas, when you try to access `/test` endpoint, you will see a
login page with QRCode but if `--no-passoword-less` option is set then you will
see login form with username and password textboxes. You can either provide
username and passoword (in case of `--no-passoword-less`) or scan the QRCode
using `Hypersign Mobile app` to authenticate youself. Once authenticated, you
can see access the protected resource i.e `This is protected` in this case. 

The `/test` endpoint is protected using `keycloak.protect()` middleware which
authenticates the user using keycloak and hs-auth servers and redirects the call
to the provided `REDIRECT_URI`. You can donwload the full node js from
[here](https://github.com/keycloak/keycloak-nodejs-connect/tree/master/example).

## Further reading

* [how does it work?](https://github.com/hypermine-bc/hypersign/blob/master/docs/overview.md#how-does-it-work) 
* [registration & login flow](https://github.com/hypermine-bc/hypersign/blob/master/docs/registration_%26_login.md#registration)

## Disclaimer

The software is still in testing phase and we're still experimenting with
cryptographic protocols supported within. Don't use it (for now) in production!
