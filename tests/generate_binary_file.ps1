# Ref: https://learn.microsoft.com/en-us/dotnet/api/system.random.nextbytes
# Ref: https://learn.microsoft.com/en-us/dotnet/api/system.io.file.writeallbytes

# 1. Initialize an 8KB byte array (8KB = 8192 bytes)
$size = "8KB"
$byteArray = New-Object byte[] $size

# 2. Fill the array with random bytes
$random = [System.Random]::new()
$random.NextBytes($byteArray)

# 3. Define the file path (Using $PWD ensures .NET writes to the correct PS directory)
$filePath = Join-Path -Path $PSScriptRoot -ChildPath "test_ls/test_binary_file"

# 4. Write the byte array directly to the file system
[System.IO.File]::WriteAllBytes($filePath, $byteArray)

Write-Host "Created 8KB random binary file at: $filePath"
