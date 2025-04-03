<?php
$ip = php_sapi_name() === 'cli' ? '127.0.0.1' : $_SERVER['REMOTE_ADDR'];

$mysqli = new mysqli(
  getenv("DB_HOST") ?: "app1_db",
  getenv("MYSQL_USER"),
  getenv("MYSQL_PASSWORD"),
  getenv("MYSQL_DATABASE")
);

if ($mysqli->connect_errno) {
  echo "Failed to connect to MySQL: " . $mysqli->connect_error;
  exit();
}

$stmt = $mysqli->prepare("INSERT INTO visitors (ip) VALUES (?)");
$stmt->bind_param("s", $ip);
$stmt->execute();
$stmt->close();

echo "<h1>Welcome!</h1><p>Your IP $ip has been recorded.</p>";
?>
