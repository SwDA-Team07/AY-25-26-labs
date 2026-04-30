
Step-1 

-To bash, I have enter the given code, under this paragraph 

curl -s -X POST http://localhost:3000/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"email": "YOUR_EMAIL", "password": "YOUR_PASSWORD"}'


  curl -s -X POST http://localhost:3000/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@email.fake", "password": "14235"}'

-As for "YOUR_EMAIL", I have used "test@email.fake" and its password is "password": "14235".
--As its output I got this message with everything that user has in its information. 

$ curl -s -X POST http://localhost:3000/api/users/login   -H "Content-Type: applicationjson"   -d '{"email": "test@email.fake", "password": "14235"}'
{"exp":1777512374,"message":"Auth Passed","token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5ZjI4ZjU2YTI2N
TA5ZTJlM2UyMGEzNCIsImNvbGxlY3Rpb24iOiJ1c2VycyIsImVtYWlsIjoidGVzdEBlbWFpbC5mYWtlIiwicm9sZXMiOlsiYWRtaW4iLCJtemluZ2
Etb3duZXIiXSwiaWF0IjoxNzc3NTA1MTc0LCJleHAiOjE3Nzc1MTIzNzR9.nOKOVvsA2NhDWUq3oPXcRQiUFjp7GCbNRsCKj0al9uA","user":{"
id":"69f28f56a26509e2e3e20a34","firstName":"tester","lastName":"testing","roles":["admin","mzinga-owner"],"apiKey
":null,"email":"test@email.fake","createdAt":"2026-04-29T23:08:06.055Z","updatedAt":"2026-04-29T23:24:32.851Z","l
oginAttempts":0}}

--- We also get our "id" for testing our fetch and patch process.

    id":"69f28f56a26509e2e3e20a34"

Step-2

-From the message, we extract our admin user's token, which is:

token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5ZjI4ZjU2YTI2NTA5ZTJlM2UyMGEzNCIsImNvbGxlY3Rpb24iOiJ1c2VycyIsImVtYWlsIjoidGVzdEBlbWFpbC5mYWtlIiwicm9sZXMiOlsiYWRtaW4iLCJtemluZ2Etb3duZXIiXSwiaWF0IjoxNzc3NTA1MTc0LCJleHAiOjE3Nzc1MTIzNzR9.nOKOVvsA2NhDWUq3oPXcRQiUFjp7GCbNRsCKj0al9uA

--For a quick test if the user has enough permisions we have used the code below in the bash.

curl -v http://localhost:3000/api/communications \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5ZjI4ZjU2YTI2NTA5ZTJlM2UyMGEzNCIsImNvbGxlY3Rpb24iOiJ1c2VycyIsImVtYWlsIjoidGVzdEBlbWFpbC5mYWtlIiwicm9sZXMiOlsiYWRtaW4iLCJtemluZ2Etb3duZXIiXSwiaWF0IjoxNzc3NTA1MTc0LCJleHAiOjE3Nzc1MTIzNzR9.nOKOVvsA2NhDWUq3oPXcRQiUFjp7GCbNRsCKj0al9uA"

curl -g -s "http://localhost:3000/api/communications?where[status][equals]=pending&depth=1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5ZjI4ZjU2YTI2NTA5ZTJlM2UyMGEzNCIsImNvbGxlY3Rpb24iOiJ1c2VycyIsImVtYWlsIjoidGVzdEBlbWFpbC5mYWtlIiwicm9sZXMiOlsiYWRtaW4iLCJtemluZ2Etb3duZXIiXSwiaWF0IjoxNzc3NTA1MTc0LCJleHAiOjE3Nzc1MTIzNzR9.nOKOVvsA2NhDWUq3oPXcRQiUFjp7GCbNRsCKj0al9uA"

--for its output we get everything in the as raw or/and populated references

* Host localhost:3000 was resolved.
* IPv6: ::1
* IPv4: 127.0.0.1
*   Trying [::1]:3000...
* Established connection to localhost (::1 port 3000) from ::1 port 60647
* using HTTP/1.x
> GET /api/communications HTTP/1.1
> Host: localhost:3000
> User-Agent: curl/8.17.0
> Accept: */*
> Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5ZjI4ZjU2YTI2NTA5ZTJlM2UyMGEzNCIsImNvbGxl
Y3Rpb24iOiJ1c2VycyIsImVtYWlsIjoidGVzdEBlbWFpbC5mYWtlIiwicm9sZXMiOlsiYWRtaW4iLCJtemluZ2Etb3duZXIiXSwiaWF0IjoxNzc3N
TA1MTc0LCJleHAiOjE3Nzc1MTIzNzR9.nOKOVvsA2NhDWUq3oPXcRQiUFjp7GCbNRsCKj0al9uA
>
< HTTP/1.1 200 OK
< X-Powered-By: Express
< X-RateLimit-Limit: 10000
< X-RateLimit-Remaining: 9999
< Date: Wed, 29 Apr 2026 23:30:52 GMT
< X-RateLimit-Reset: 1777505457
< Content-Language: en
< Set-Cookie: lng=en; Path=/; Expires=Thu, 29 Apr 2027 23:30:52 GMT; SameSite=Strict
< Access-Control-Allow-Methods: PUT, PATCH, POST, GET, DELETE, OPTIONS
< Access-Control-Allow-Headers: Origin, X-Requested-With, Content-Type, Accept, Authorization, Content-Encoding,
x-apollo-tracing
< Access-Control-Allow-Origin: *
< Content-Type: application/json; charset=utf-8
< Content-Length: 624
< ETag: W/"270-un7c88CdjaBJpEVQPhZAesngOZs"
< Vary: Accept-Encoding
< Connection: keep-alive
< Keep-Alive: timeout=5
<
{"docs":[{"id":"69f2934ba26509e2e3e20a53","subject":"Test 2","tos":[{"relationTo":"users","value":{"id":"69f28f56
a26509e2e3e20a34","firstName":"tester","lastName":"testing","roles":["admin","mzinga-owner"],"apiKey":null,"email
":"test@email.fake","createdAt":"2026-04-29T23:08:06.055Z","updatedAt":"2026-04-29T23:24:32.851Z","loginAttempts"
:0}}],"body":[{"children":[{"text":"test2"}]}],"status":"pending","createdAt":"2026-04-29T23:24:59.900Z","updated
At":"2026-04-29T23:24:59.900Z"}],"totalDocs":1,"limit":10,"totalPages":1,"page":1,"pagingCounter":1,"hasPrevPage"
:false,"hasNextPage":false,"prevPage":null,"nextPage":null}* Connection #0 to host localhost:3000 left intact

---Lets fetch our singlular document/mail with the code below

curl -g -s "http://localhost:3000/api/communications/69f2934ba26509e2e3e20a53?depth=1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5ZjI4ZjU2YTI2NTA5ZTJlM2UyMGEzNCIsImNvbGxlY3Rpb24iOiJ1c2VycyIsImVtYWlsIjoidGVzdEBlbWFpbC5mYWtlIiwicm9sZXMiOlsiYWRtaW4iLCJtemluZ2Etb3duZXIiXSwiaWF0IjoxNzc3NTA1MTc0LCJleHAiOjE3Nzc1MTIzNzR9.nOKOVvsA2NhDWUq3oPXcRQiUFjp7GCbNRsCKj0al9uA"

---As a result, we get the output as:

{"id":"69f2934ba26509e2e3e20a53","subject":"Test 2","tos":[{"relationTo":"users","value":{"id":"69f28f56a26509e2e3e20a34","firstName":"tester","lastName":"testing","roles":["admin","mzinga-owner"],"apiKey":null,"email":"test@email.fake","createdAt":"2026-04-29T23:08:06.055Z","updatedAt":"2026-04-29T23:24:32.851Z","loginAttempts":0}}],"body":[{"children":[{"text":"test2"}]}],"status":"pending","createdAt":"2026-04-29T23:24:59.900Z","updatedAt":"2026
-04-29T23:24:59.900Z"}

---From this, we can see "tos" values. 

    Step-3

-Now that we see what currently the document have as it's values, lets use PATCH and update it's status as "sent". I used the code below for it to happen 

curl -s -X PATCH http://localhost:3000/api/communications/69f2934ba26509e2e3e20a53 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY5ZjI4ZjU2YTI2NTA5ZTJlM2UyMGEzNCIsImNvbGxlY3Rpb24iOiJ1c2VycyIsImVtYWlsIjoidGVzdEBlbWFpbC5mYWtlIiwicm9sZXMiOlsiYWRtaW4iLCJtemluZ2Etb3duZXIiXSwiaWF0IjoxNzc3NTA1MTc0LCJleHAiOjE3Nzc1MTIzNzR9.nOKOVvsA2NhDWUq3oPXcRQiUFjp7GCbNRsCKj0al9uA" \
  -H "Content-Type: application/json" \
  -d '{"status": "sent"}'

- as its output we got this message.

{"message":"Updated successfully.","doc":{"id":"69f2934ba26509e2e3e20a53","subject":"Test 2","tos":[{"relationTo":"users","value":{"id":"69f28f56a26509e2e3e20a34","firstName":"tester","lastName":"testing","roles":["admin","mzinga-owner"],"apiKey":null,"email":"test@email.fake","createdAt":"2026-04-29T23:08:06.055Z","updatedAt":"2026-04-29T23:24:32.851Z","loginAttempts":0}}],"body":[{"children":[{"text":"test2"}]}],"status":"sent","createdAt":"2026-04-29T23:24:59.900Z","updatedAt":"2026-04-29T23:50:32.217Z"}}

-- As seen in the "status" part, it has changed to sent from pending.

In the screenshots, the changes can be seen as a photo. With this test, we explored "/api/communications" endpoint using "curl" and "JWT" token. We saw that using "depth=1" we can directly access emails directly, to be used and update its values directly, successfully.

--END FILE--