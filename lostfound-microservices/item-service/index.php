<?php

header("Content-Type: application/json");

/**
 * Call another microservice over the Docker network (using its service name).
 * Returns the decoded JSON body, or null if the call failed / timed out /
 * returned a non-200 status.
 */
function callService(string $url): ?array
{
    $context = stream_context_create([
        "http" => [
            "timeout"       => 3,      // seconds - never hang forever
            "ignore_errors" => true,   // still read the body on 4xx/5xx
        ],
    ]);

    $body = @file_get_contents($url, false, $context);

    if ($body === false) {
        return null;
    }

    // $http_response_header is populated by file_get_contents
    $statusLine = $http_response_header[0] ?? "";
    if (strpos($statusLine, " 200") === false) {
        return null;
    }

    $decoded = json_decode($body, true);
    return is_array($decoded) ? $decoded : null;
}

if ($_SERVER["REQUEST_METHOD"] === "GET") {

    // Contact User Service and Handover Service using Docker service names
    $userResponse     = callService("http://user-service/");
    $handoverResponse = callService("http://handover-service/");

    // If a dependency is down, report it honestly instead of returning 200
    if ($userResponse === null || $handoverResponse === null) {
        http_response_code(502);

        echo json_encode([
            "service" => "Item Service",
            "status"  => "error",
            "message" => "Could not reach one or more downstream services",
            "user_service_reachable"     => $userResponse !== null,
            "handover_service_reachable" => $handoverResponse !== null
        ]);
        exit;
    }

    echo json_encode([
        "service" => "Item Service",
        "status" => "running",
        "message" => "Item service successfully communicated with other services",
        "user_service" => $userResponse,
        "handover_service" => $handoverResponse
    ]);

} else {

    http_response_code(405);
    header("Allow: GET");

    echo json_encode([
        "error" => "Method not allowed"
    ]);
}
