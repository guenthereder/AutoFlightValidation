const express = require('express');
const app = express();
const fs = require('fs');
const { OAuth2Client } = require('google-auth-library');

const config = JSON.parse(fs.readFileSync('__google_token.json'));

const client = new OAuth2Client({
  clientId: config.client_id,
  clientSecret: config.client_secret,
  redirectUri: 'http://localhost:8000/callback',
});


app.get('/callback', async (req, res) => {
  const authorizationCode = req.query.code; // Extract the authorization code from the query parameters

  try {
    const { tokens } = await client.getToken(authorizationCode);
    const token = tokens.access_token;
    const refresh_token = tokens.refresh_token;
    const token_uri = "https://oauth2.googleapis.com/token";
    const client_id = client.client_id;
    const client_secret = client.client_secret;

    // Write the token to a JSON file
    const tokenData = JSON.stringify({ token, refresh_token, token_uri, client_id, client_secret });
    fs.writeFileSync('__google_token_new.json', tokenData);

    // Redirect the user to a success page or display a success message
    res.send('Authorization successful! You can close this page now.');
  } catch (error) {
    console.error('Error exchanging authorization code for tokens:', error);
    // Handle the error and display an error message to the user
    res.send('Error occurred during authorization.');
  }
});

const port = 8000; // Replace with the desired port number
app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
