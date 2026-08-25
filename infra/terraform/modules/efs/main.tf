resource "aws_security_group" "efs" {
  name        = "${var.project_name}-efs-${var.environment}"
  description = "Allow NFS traffic from EKS"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_efs_file_system" "jenkins" {
  creation_token = "${var.project_name}-jenkins-${var.environment}"
  encrypted      = true
  tags = {
    Name = "${var.project_name}-jenkins-${var.environment}"
  }
}

resource "aws_efs_mount_target" "jenkins" {
  count           = length(var.subnet_ids)
  file_system_id  = aws_efs_file_system.jenkins.id
  subnet_id       = var.subnet_ids[count.index]
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "jenkins" {
  file_system_id = aws_efs_file_system.jenkins.id
  posix_user {
    gid = 1000
    uid = 1000
  }
  root_directory {
    path = "/jenkins"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "0755"
    }
  }
}