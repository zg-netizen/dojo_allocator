# Contributing to Dojo Allocator

Thank you for your interest in contributing to Dojo Allocator! This document provides guidelines and instructions for contributing.

## 🤝 How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/zg-netizen/dojo_allocator/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Docker version, etc.)

### Suggesting Features

1. Open an issue with the `enhancement` label
2. Describe the feature and its use case
3. Discuss implementation approach if possible

### Code Contributions

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
   - Follow existing code style
   - Add tests if applicable
   - Update documentation
4. **Commit your changes**
   ```bash
   git commit -m "Add: description of your changes"
   ```
5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```
6. **Create a Pull Request**

## 📋 Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and small
- Add type hints where appropriate

## 🧪 Testing

- Write tests for new features
- Ensure all tests pass before submitting PR
- Test with Docker Compose environment

## 📝 Commit Messages

Use clear, descriptive commit messages:
- `Add: feature description`
- `Fix: bug description`
- `Update: component description`
- `Refactor: what was refactored`

## 🔍 Code Review Process

1. All PRs will be reviewed
2. Address review comments promptly
3. Keep PRs focused and reasonably sized
4. Update documentation as needed

## 📚 Documentation

- Update README.md if adding major features
- Add docstrings to new functions/classes
- Update API documentation if endpoints change

## ⚠️ Security

- **NEVER** commit `.env` files or API keys
- Report security issues privately
- Follow responsible disclosure

Thank you for contributing! 🎉

