provider "aws" {
  region  = var.source_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = var.name_prefix
      Environment = "lab"
      ManagedBy   = "Terraform"
    }
  }
}

provider "aws" {
  alias   = "destination"
  region  = var.destination_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = var.name_prefix
      Environment = "lab"
      ManagedBy   = "Terraform"
    }
  }
}