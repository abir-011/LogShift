data "aws_instance" "logshift" {
  instance_id = "i-0a5fb35c151a5e0df"
}

output "logshift_ec2_details" {
  value = {
    instance_id   = data.aws_instance.logshift.id
    instance_type = data.aws_instance.logshift.instance_type
    public_ip     = data.aws_instance.logshift.public_ip
    private_ip    = data.aws_instance.logshift.private_ip
    state         = data.aws_instance.logshift.instance_state
    subnet_id     = data.aws_instance.logshift.subnet_id
  }
}

data "aws_ecr_repository" "logshift" {
  name = "logshift"
}

output "logshift_ecr_details" {
  value = {
    repository_name = data.aws_ecr_repository.logshift.name
    repository_url  = data.aws_ecr_repository.logshift.repository_url
    registry_id     = data.aws_ecr_repository.logshift.registry_id
  }
}

data "aws_iam_role" "logshift_ec2" {
  name = "LogShiftEC2ECRRole"
}

output "logshift_iam_role_details" {
  value = {
    role_name   = data.aws_iam_role.logshift_ec2.name
    role_arn    = data.aws_iam_role.logshift_ec2.arn
    role_id     = data.aws_iam_role.logshift_ec2.unique_id
    create_date = data.aws_iam_role.logshift_ec2.create_date
  }
}

data "aws_security_group" "logshift" {
  id = "sg-0895546aba39e1b69"
}

output "logshift_security_group_details" {
  value = {
    name        = data.aws_security_group.logshift.name
    id          = data.aws_security_group.logshift.id
    description = data.aws_security_group.logshift.description
    vpc_id      = data.aws_security_group.logshift.vpc_id
  }
}

data "aws_iam_instance_profile" "logshift" {
  name = "LogShiftEC2ECRRole"
}

output "logshift_instance_profile_details" {
  value = {
    name = data.aws_iam_instance_profile.logshift.name
    arn  = data.aws_iam_instance_profile.logshift.arn
    id   = data.aws_iam_instance_profile.logshift.id
  }
}

data "aws_subnet" "logshift" {
  id = "subnet-0a32e525930640eb5"
}

output "logshift_subnet_details" {
  value = {
    id                = data.aws_subnet.logshift.id
    availability_zone = data.aws_subnet.logshift.availability_zone
    cidr_block        = data.aws_subnet.logshift.cidr_block
    vpc_id            = data.aws_subnet.logshift.vpc_id
  }
}

data "aws_vpc" "logshift" {
  id = "vpc-0cdb8cbe431716cee"
}

output "logshift_vpc_details" {
  value = {
    id         = data.aws_vpc.logshift.id
    cidr_block = data.aws_vpc.logshift.cidr_block
    state      = data.aws_vpc.logshift.state
    is_default = data.aws_vpc.logshift.default
  }
}
resource "aws_ecr_repository" "logshift" {
  name                 = "logshift"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = false
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_instance" "logshift" {
  ami                         = "ami-0c4c0d31978150116"
  instance_type               = "t3.small"
  key_name                    = "logshift_kp"
  subnet_id                   = "subnet-0a32e525930640eb5"
  vpc_security_group_ids      = ["sg-0895546aba39e1b69"]
  iam_instance_profile        = "LogShiftEC2ECRRole"
  associate_public_ip_address = true
  ebs_optimized               = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 12
    iops                  = 3000
    throughput            = 125
    encrypted             = false
    delete_on_termination = true
  }

  tags = {
    Name = "LogShift-EC2"
  }
}

resource "aws_security_group" "logshift" {
  name        = "launch-wizard-1"
  description = "launch-wizard-1 created 2026-11-09T18:47:40.535Z"
  vpc_id      = "vpc-0cdb8cbe431716cee"

  ingress {
    description = "LogShift dashboard access"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["49.37.10.246/32"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["49.37.10.246/32"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {}
}

resource "aws_iam_role" "logshift_ec2" {
  name                 = "LogShiftEC2ECRRole"
  path                 = "/"
  description          = "Allow LogShift EC2 instance to pull Docker images from private ECR."
  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecr_readonly" {
  role       = aws_iam_role.logshift_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.logshift_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "logshift" {
  name = "LogShiftEC2ECRRole"
  role = aws_iam_role.logshift_ec2.name
}

