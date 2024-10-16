# Use a minimal base image
FROM alpine:latest

# Install OpenSSH
RUN apk add --no-cache openssh

# Create a user with a specific password
RUN adduser -D -s /bin/sh testuser && \
    echo "testuser:testpassword" | chpasswd

# Generate SSH host keys
RUN ssh-keygen -A

# Enable SSH root login and password authentication
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    echo "PermitEmptyPasswords no" >> /etc/ssh/sshd_config

# Expose SSH port
EXPOSE 22

# Start the SSH service
CMD ["/usr/sbin/sshd", "-D"]
