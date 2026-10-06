<?php

header("Content-Type: application/json");

if ($_SERVER["REQUEST_METHOD"] === "GET") {

    echo json_encode([
        "service" => "Handover Service",
        "status" => "running",
        "message" => "Handover service is working"
    ]);

} else {

    http_response_code(405);

    echo json_encode([
        "error" => "Method not allowed"
    ]);
}

?>