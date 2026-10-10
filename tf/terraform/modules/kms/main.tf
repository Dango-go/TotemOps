resource "aws_kms_key" "this" {
  description             = var.description
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags = {
    Name = var.key_name
  }
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.key_name}"
  target_key_id = aws_kms_key.this.key_id
}