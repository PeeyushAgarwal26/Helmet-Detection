#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "Peeyush's S24 Ultra";
const char* password = "peeyush26";

const int buzzerPin = 2;
const int ledPin = 4;

WebServer server(80);

String serialCommand;

void handleBuzzOn() {
    digitalWrite(buzzerPin, HIGH); // Turn the buzzer ON
    digitalWrite(ledPin, HIGH); // Turn the buzzer ON
    server.send(200, "text/plain", "Buzzer is now ON");
    Serial.println("Request received: /buzz_on. Buzzer turned ON.");
}

// Function to handle the "/buzz_off" request
void handleBuzzOff() {
    digitalWrite(buzzerPin, LOW); // Turn the buzzer OFF
    digitalWrite(ledPin, LOW); // Turn the buzzer OFF
    server.send(200, "text/plain", "Buzzer is now OFF");
    Serial.println("Request received: /buzz_off. Buzzer turned OFF.");
}

// Function to handle the root URL "/"
void handleRoot() {
    String status = digitalRead(buzzerPin) ? "ON" : "OFF";
    String html = "<h1>ESP Buzzer Controller</h1>";
    html += "<p>Buzzer Status: <strong>" + status + "</strong></p>";
    server.send(200, "text/html", html);
    Serial.println("Request received: /. Status page sent.");
}

// Function to handle requests to non-existent pages
void handleNotFound() {
    server.send(404, "text/plain", "404: Not Found");
}

// --- Main Setup ---
void setup() {
    // Start serial communication for debugging
    Serial.begin(115200);
    delay(10);
    Serial.println("\n--- ESP Buzzer Controller ---");

    // Set the buzzer pin as an output
    pinMode(buzzerPin, OUTPUT);
    pinMode(ledPin, OUTPUT);
    digitalWrite(buzzerPin, LOW); // Ensure buzzer is off initially
    digitalWrite(ledPin, LOW); // Ensure LED is off initially

    // Connect to the WiFi network
    Serial.print("Connecting to ");
    Serial.println(ssid);
    WiFi.begin(ssid, password);

    // Wait for the connection to be established
    int retries = 0;
    while (WiFi.status() != WL_CONNECTED && retries < 20) {
        delay(500);
        Serial.print(".");
        retries++;
    }

    // Check if connection was successful
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi connected!");
        Serial.print("IP address: ");
        Serial.println(WiFi.localIP());

        // Define the server's routes
        server.on("/", HTTP_GET, handleRoot);
        server.on("/buzz_on", HTTP_GET, handleBuzzOn);
        server.on("/buzz_off", HTTP_GET, handleBuzzOff);
        
        // Set up a handler for pages that are not found
        server.onNotFound(handleNotFound);

        // Start the web server
        server.begin();
        Serial.println("HTTP server started. Waiting for requests...");
    } else {
        Serial.println("\nFailed to connect to WiFi. Please check credentials.");
        // Blink an LED or take other action to indicate failure
    }
}

// --- Main Loop ---
void loop() {
    // 1. Handle any incoming client requests
    server.handleClient();

    // 2. Handle any incoming Serial port commands
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n') { // Command is complete when a newline is received
            serialCommand.trim(); // Remove any whitespace
            if (serialCommand.equals("buzz_on")) {
                digitalWrite(buzzerPin, HIGH);
                digitalWrite(ledPin, HIGH);
                Serial.println("Serial command received: buzz_on. Buzzer ON.");
            } else if (serialCommand.equals("buzz_off")) {
                digitalWrite(buzzerPin, LOW);
                digitalWrite(ledPin, LOW);
                Serial.println("Serial command received: buzz_off. Buzzer OFF.");
            }
            serialCommand = ""; // Clear for the next command
        } else {
            serialCommand += c;
        }
    }

}