<?php

header("Content-Type: application/json");

if ($_SERVER["REQUEST_METHOD"] === "GET") {

    echo json_encode([
        "service" => "User Service",
        "status" => "running",
        "message" => "User service is working"
    ]);

} else {

    http_response_code(405);

    echo json_encode([
        "error" => "Method not allowed"
    ]);
}

?>